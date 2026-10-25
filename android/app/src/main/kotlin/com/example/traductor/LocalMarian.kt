package com.example.traductor

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Rect
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.security.MessageDigest
import java.text.Normalizer
import java.util.concurrent.locks.ReentrantReadWriteLock
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.read
import kotlin.concurrent.write

/** Bundled EN→ES model. No requests or downloads are made by this engine. */
data class LocalTranslation(val text:String,val retainedOriginal:Boolean,val reason:String)
data class LocalLineRead(val text:String,val confidence:Float,val systemAgreement:Boolean)

class LocalMarian(context: Context) : AutoCloseable {
    companion object {
        private val files = listOf("tokenizer.json", "terminology.json", "ocr-characters.json", "ocr-characters-fallback.json")
        init {
            System.loadLibrary("onnxruntime")
            System.loadLibrary("luma_local")
        }
        private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        @Synchronized private fun prepare(context: Context): File {
            val prefix = "flutter_assets/assets/models/opus-en-es/"
            val manifestBytes = context.assets.open(prefix + "manifest.json").use { it.readBytes() }
            val manifest = JSONObject(String(manifestBytes, Charsets.UTF_8))
            val key = digest(manifestBytes)
            val directory = File(context.noBackupFilesDir, "models/opus-en-es")
            directory.mkdirs()
            val marker = File(directory, "verified.sha256")
            if (marker.exists() && marker.readText() == key && files.all { File(directory, it).length() > 0 }) return directory
            for (name in files) {
                val expected = manifest.getJSONObject("files").getString(name)
                val file = File(directory, name)
                val partial = File(directory, "$name.partial")
                val hash = MessageDigest.getInstance("SHA-256")
                context.assets.open(prefix + name).use { input ->
                    partial.outputStream().use { output ->
                        val buffer = ByteArray(1024 * 1024)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            hash.update(buffer, 0, count)
                            output.write(buffer, 0, count)
                        }
                    }
                }
                val actual = hash.digest().joinToString("") { "%02x".format(it) }
                check(actual == expected) { "El modelo local está dañado: $name" }
                check(partial.renameTo(file)) { "No se pudo preparar el modelo local. Comprueba el espacio disponible." }
            }
            marker.writeText(key)
            return directory
        }
    }
    private val lock = ReentrantReadWriteLock()
    private val detectionGeneration=AtomicLong(0)
    // ONNX weights are read from APK assets (mapped or decompressed in native
    // memory), without a second copy on disk. Only metadata is extracted.
    private var handle = nativeCreate(prepare(context.applicationContext).absolutePath,context.assets)
    fun translate(text: String): String = translateDetailed(text).text
    fun translateDetailed(text: String): LocalTranslation = lock.read {
        check(handle != 0L) { "El traductor ya está cerrado." }
        val normalized = Normalizer.normalize(text, Normalizer.Form.NFKC)
        val result=JSONObject(String(nativeTranslate(handle, normalized.toByteArray(Charsets.UTF_8)), Charsets.UTF_8))
        LocalTranslation(result.getString("translation"),result.optBoolean("retained_original"),result.optString("reason"))
    }
    fun tokenize(text: String): LongArray = lock.read {
        check(handle != 0L)
        nativeTokenize(handle, Normalizer.normalize(text, Normalizer.Form.NFKC).toByteArray(Charsets.UTF_8))
    }
    fun recognizeLine(bitmap: Bitmap, rect: Rect): Pair<String,Float>? = lock.read {
        if(handle==0L)return@read null
        val pixels=IntArray(rect.width()*rect.height())
        bitmap.getPixels(pixels,0,rect.width(),rect.left,rect.top,rect.width(),rect.height())
        val output=nativeRecognize(handle,pixels,rect.width(),rect.height()) ?: return@read null
        val result=JSONObject(String(output,Charsets.UTF_8));result.getString("text") to result.getDouble("confidence").toFloat()
    }
    fun cancel() = lock.read { if (handle != 0L) { detectionGeneration.incrementAndGet();nativeCancel(handle) } }
    fun recognizeLineWithHint(bitmap: Bitmap, rect: Rect, systemText: String): LocalLineRead? = lock.read {
        if(handle==0L)return@read null
        val pixels=IntArray(rect.width()*rect.height())
        bitmap.getPixels(pixels,0,rect.width(),rect.left,rect.top,rect.width(),rect.height())
        val output=nativeRecognizeWithHint(handle,pixels,rect.width(),rect.height(),systemText.toByteArray(Charsets.UTF_8)) ?: return@read null
        val result=JSONObject(String(output,Charsets.UTF_8))
        LocalLineRead(result.getString("text"),result.getDouble("confidence").toFloat(),result.optBoolean("system_agreement"))
    }
    fun findAdditionalText(bitmap: Bitmap, existing: List<Rect>): List<ComicRegion> = lock.read {
        if(handle==0L)return@read emptyList()
        val generation=detectionGeneration.get()
        require(bitmap.width<=4096&&bitmap.height<=4096)
        val pixels=IntArray(bitmap.width*bitmap.height)
        bitmap.getPixels(pixels,0,bitmap.width,0,0,bitmap.width,bitmap.height)
        val boxes=IntArray(existing.size*4)
        existing.forEachIndexed { index, rect -> boxes[index*4]=rect.left;boxes[index*4+1]=rect.top;boxes[index*4+2]=rect.right;boxes[index*4+3]=rect.bottom }
        if(generation!=detectionGeneration.get())return@read emptyList()
        val bytes=nativeDetect(handle,pixels,bitmap.width,bitmap.height,boxes,generation) ?: return@read emptyList()
        if(generation!=detectionGeneration.get())return@read emptyList()
        val result=JSONArray(String(bytes,Charsets.UTF_8))
        (0 until result.length()).map { index ->
            val item=result.getJSONObject(index);val bounds=item.getJSONArray("bounds")
            ComicRegion(Rect(bounds.getInt(0),bounds.getInt(1),bounds.getInt(2),bounds.getInt(3)),item.getString("text"),
                confidence=item.getDouble("confidence").toFloat(),additionalDetection=true)
        }
    }
    override fun close() = lock.write { if (handle != 0L) { nativeDestroy(handle); handle = 0 } }
    private external fun nativeCreate(directory: String, assets: android.content.res.AssetManager): Long
    private external fun nativeTranslate(handle: Long, source: ByteArray): ByteArray
    private external fun nativeTokenize(handle: Long, source: ByteArray): LongArray
    private external fun nativeRecognize(handle: Long, source: IntArray, width: Int, height: Int): ByteArray?
    private external fun nativeRecognizeWithHint(handle: Long, source: IntArray, width: Int, height: Int, systemText: ByteArray): ByteArray?
    private external fun nativeCancel(handle: Long)
    private external fun nativeDetect(handle: Long, pixels: IntArray, width: Int, height: Int, existing: IntArray, generation: Long): ByteArray?
    private external fun nativeDestroy(handle: Long)
}
