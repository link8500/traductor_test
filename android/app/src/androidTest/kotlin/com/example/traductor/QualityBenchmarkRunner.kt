package com.example.traductor

import android.app.Activity
import android.app.Instrumentation
import android.graphics.*
import android.os.Bundle
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.zip.ZipInputStream
import java.util.zip.GZIPOutputStream
import java.io.ByteArrayOutputStream
import android.os.ParcelFileDescriptor
import android.util.Base64

/** Sideload-only instrumentation; not present in the distributed application. */
class QualityBenchmarkRunner : Instrumentation() {
    private var options=Bundle()
    override fun onCreate(arguments: Bundle?) { super.onCreate(arguments); options=arguments?:Bundle(); start() }
    override fun onStart() {
        if(options.getString("probe")=="ocr-lines") { LineSelectionProbe.run(this,options);return }
        if(options.containsKey("probe")) { ArmKernelProbe.run(this,options);return }
        val root=File(targetContext.filesDir,"comic-quality")
        root.mkdirs()
        val full=options.getString("mode")=="full"
        val report=File(root,if(full) "android-full.jsonl" else "ocr.jsonl")
        val summary=JSONArray()
        var images=0; var crops=0; var regions=0
        var failures=0
        val translations=HashMap<String,LocalTranslation>()
        var recognizer: com.google.mlkit.vision.text.TextRecognizer?=null
        var local:LocalMarian?=null
        try {
            if (options.getString("import")=="true") {
                ParcelFileDescriptor.AutoCloseInputStream(uiAutomation.executeShellCommand("cat /data/local/tmp/luma-quality-fixtures.zip")).use { input ->
                    ZipInputStream(input).use { zip ->
                        while (true) {
                            val entry=zip.nextEntry ?: break
                            val target=File(root,entry.name)
                            check(target.canonicalPath.startsWith(root.canonicalPath+File.separator)) { "Unsafe fixture path" }
                            if (entry.isDirectory) target.mkdirs() else { target.parentFile?.mkdirs();target.outputStream().use { zip.copyTo(it) } }
                            zip.closeEntry()
                        }
                    }
                }
            }
            if (options.getString("mode")=="model") { testModel(root); return }
            recognizer=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            local=LocalMarian(targetContext)
            val manifest=JSONArray(File(root,"manifest.json").readText())
            report.bufferedWriter().use { output ->
                for (chapterIndex in 0 until manifest.length()) {
                    val chapter=manifest.getJSONObject(chapterIndex)
                    val chapterImages=chapter.getJSONArray("images")
                    var chapterRegions=0
                    for (imageIndex in 0 until chapterImages.length()) {
                        val entry=chapterImages.getJSONObject(imageIndex)
                        val file=File(root,entry.getString("path"))
                        val decoder=BitmapRegionDecoder.newInstance(file.absolutePath,false)
                        requireNotNull(decoder) { "Cannot decode ${file.name}" }
                        val previous=ArrayList<Pair<Rect,String>>()
                        try {
                            var top=0
                            while (top<decoder.height) {
                                val bottom=minOf(top+2000,decoder.height)
                                val bitmap=decoder.decodeRegion(Rect(0,top,decoder.width,bottom),BitmapFactory.Options().apply { inPreferredConfig=Bitmap.Config.ARGB_8888 })
                                try {
                                    val recognized=ComicOcr.recognize(recognizer!!,bitmap,local)
                                    for (region in recognized) {
                                        val text=normalizeScreenText(region.text)
                                        if (text.count { it.isLetter() }<2) continue
                                        if (top>0 && region.bounds.top<18 || bottom<decoder.height && region.bounds.bottom>bitmap.height-18) continue
                                        val global=Rect(region.bounds).apply { offset(0,top) }
                                        val duplicate=previous.any { (old,oldText) ->
                                            val overlap=Rect()
                                            Rect.intersects(old,global) && overlap.setIntersect(old,global) &&
                                                overlap.width()*overlap.height()>minOf(old.width()*old.height(),global.width()*global.height())*.70 &&
                                                (oldText==text || oldText.contains(text) || text.contains(oldText))
                                        }
                                        if (duplicate) continue
                                        previous.add(global to text)
                                        val record=JSONObject().put("chapter",chapter.getString("id")).put("image",imageIndex).put("cropTop",top)
                                            .put("bounds",JSONArray(listOf(global.left,global.top,global.right,global.bottom))).put("raw",region.text)
                                            .put("source",text).put("native_source",region.nativeText).put("centered",region.centered).put("confidence",region.confidence).put("lineHeight",region.lineHeight)
                                        if(full) {
                                            val time=System.nanoTime()
                                            try {
                                                val translated=translations.getOrPut(text) { local!!.translateDetailed(text) }
                                                record.put("translation",translated.text).put("retained_original",translated.retainedOriginal)
                                                if(translated.retainedOriginal)record.put("reason",translated.reason)
                                            }
                                            catch(error:Exception) {record.put("error",error.message);failures++}
                                            record.put("milliseconds",(System.nanoTime()-time)/1_000_000)
                                        }
                                        output.write(record.toString());output.newLine();regions++;chapterRegions++
                                    }
                                } finally { bitmap.recycle() }
                                crops++
                                if (bottom==decoder.height) break
                                top+=1300
                            }
                        } finally { decoder.recycle() }
                        images++;output.flush()
                        sendStatus(0,Bundle().apply { putString("stream","${chapter.getString("id")} image ${imageIndex+1}/${chapterImages.length()} · $regions regions\n") })
                    }
                    summary.put(JSONObject().put("chapter",chapter.getString("id")).put("images",chapterImages.length()).put("regions",chapterRegions))
                }
            }
            val summaryName=if(full) "android-full-summary.json" else "ocr-summary.json"
            File(root,summaryName).writeText(JSONObject().put("images",images).put("viewports",crops).put("regions",regions).put("runtime_errors",failures).put("chapters",summary).toString(2))
            exportFile(root,report.name);exportFile(root,summaryName)
            finish(Activity.RESULT_OK,Bundle().apply { putString("stream","OCR completed: $images images, $crops viewports, $regions regions\n");putString("report",report.absolutePath) })
        } catch (error:Throwable) {
            File(root,"ocr-error.txt").writeText(error.stackTraceToString())
            finish(Activity.RESULT_CANCELED,Bundle().apply { putString("stream",error.stackTraceToString()) })
        } finally { local?.close();recognizer?.close() }
    }

    private fun testModel(root: File) {
        val started=System.nanoTime()
        LocalMarian(targetContext).use { model ->
            val cases=JSONArray(context.assets.open("tokenizer_cases.json").bufferedReader().use { it.readText() })
            for (index in 0 until cases.length()) {
                val item=cases.getJSONObject(index);val expected=item.getJSONArray("tokens")
                val actual=model.tokenize(item.getString("source"))
                check(actual.size==expected.length() && actual.indices.all { actual[it]==expected.getLong(it) }) { "Tokenizer mismatch $index: ${actual.joinToString()} expected $expected" }
            }
            val repairs=JSONArray(context.assets.open("ocr-normalization-cases.json").bufferedReader().use { it.readText() })
            var repairCases=0
            for(index in 0 until repairs.length()) {
                val item=repairs.getJSONObject(index)
                val fragments=item.optJSONArray("target_any") ?: continue
                val translated=model.translate(item.getString("source"))
                check((0 until fragments.length()).any { translated.contains(fragments.getString(it),true) }) { "OCR repair did not survive native Android inference: $translated" }
                repairCases++
            }
            val fixture=listOf(ComicRegion(Rect(200,100,500,140),"FIRST, FOUR DAYS IN",lineHeight=40f),
                ComicRegion(Rect(100,148,600,280),"THE WILDERNESS WAS\nENOUGH TIME.",lineHeight=40f),
                ComicRegion(Rect(200,500,500,540),"ANOTHER BALLOON",lineHeight=40f))
            check(ComicText.mergeParagraphs(fixture).size==2) { "Paragraph geometry regression" }
            val spaced=listOf(ComicRegion(Rect(100,100,700,140),"AFTER FOUR DAYS IN THE",lineHeight=40f),
                ComicRegion(Rect(300,175,500,215),"FOREST,",lineHeight=40f),
                ComicRegion(Rect(100,250,700,290),"WE REACHED THE CAMP.",lineHeight=40f),
                ComicRegion(Rect(100,450,700,490),"ANOTHER BALLOON",lineHeight=40f))
            check(ComicText.mergeParagraphs(spaced).size==2) { "Large uppercase paragraph split into separate translations" }
            val lettering=Bitmap.createBitmap(600,140,Bitmap.Config.ARGB_8888)
            Canvas(lettering).apply {
                drawColor(Color.WHITE)
                drawText("Hello world",20f,90f,Paint(Paint.ANTI_ALIAS_FLAG).apply { color=Color.BLACK;textSize=56f;typeface=Typeface.DEFAULT })
            }
            val letters=model.recognizeLine(lettering,Rect(10,32,390,108))
            lettering.recycle()
            check(letters!=null&&letters.first.trim().equals("Hello world",true)&&letters.second>.8f) { "Native OCR fixture failed: $letters" }
            // The final window is translucent: verify the visible composite,
            // rather than merely checking the replacement bitmap's color.
            val checker=Bitmap.createBitmap(128,128,Bitmap.Config.ARGB_8888)
            for(y in 0 until 128)for(x in 0 until 128)checker.setPixel(x,y,if((x/4+y/4)%2==0)Color.BLACK else Color.WHITE)
            val masked=TranslationMatte.prepare(TranslatedBlock(RectF(12f,12f,116f,116f),"",Color.WHITE),checker,.8f)
            val mask=requireNotNull(masked.matte)
            var lightest=0;var darkest=255
            for(y in 24 until 104)for(x in 24 until 104) {
                val visible=(Color.red(mask.getPixel(x-masked.matteLeft,y-masked.matteTop))*.8f+Color.red(checker.getPixel(x,y))*.2f).toInt()
                lightest=maxOf(lightest,visible);darkest=minOf(darkest,visible)
            }
            check(lightest-darkest<=2&&darkest in 202..205) { "Original glyphs remain visible in the alpha mask: $darkest..$lightest" }
            TranslationMatte.release(listOf(masked));checker.recycle()
            val samples=JSONArray(File(root,"model-input.json").readText())
            File(root,"android-translations.jsonl").bufferedWriter().use { output ->
                for (index in 0 until samples.length()) {
                    val item=samples.getJSONObject(index);val time=System.nanoTime()
                    item.put("translation",model.translate(item.getString("source"))).put("milliseconds",(System.nanoTime()-time)/1_000_000)
                    output.write(item.toString());output.newLine();output.flush()
                    sendStatus(0,Bundle().apply { putString("stream","Local model ${index+1}/${samples.length()} · ${item.getLong("milliseconds")} ms\n") })
                }
            }
            var cancelled=false
            val worker=Thread { try { model.translate(("This is a long paragraph about survival at an academy. ").repeat(30)) } catch (_:IllegalStateException) { cancelled=true } }
            worker.start();Thread.sleep(150);model.cancel();worker.join(5000)
            check(!worker.isAlive && cancelled) { "The native decoder did not cancel" }
            check(model.translate("Hello world").contains("Hola",true)) { "The decoder did not recover after cancellation" }
            val incomplete="OU DAMNED FOOL, WRAP UP WHAT yOU HAVE TO DO. I'M"
            val preserved=model.translateDetailed(incomplete)
            check(preserved.retainedOriginal&&preserved.text==incomplete) { "An incomplete OCR fragment must remain original" }
            check(model.translate("Hello world").contains("Hola",true)) { "A preserved fragment must not prevent the next translation" }
            val report=JSONObject().put("tokenizer_cases",cases.length()).put("samples",samples.length()).put("cancellation",true)
                .put("ocr_repair_cases",repairCases)
                .put("paragraph_geometry",true).put("local_ocr",true).put("alpha_mask",true).put("incomplete_preserved",true).put("milliseconds",(System.nanoTime()-started)/1_000_000)
            File(root,"android-model-summary.json").writeText(report.toString(2))
            exportFile(root,"android-translations.jsonl");exportFile(root,"android-model-summary.json")
            finish(Activity.RESULT_OK,Bundle().apply { putString("stream",report.toString()) })
        }
    }
    private fun exportFile(root: File,name: String) {
        val compressed=ByteArrayOutputStream()
        GZIPOutputStream(compressed).use { output -> File(root,name).inputStream().use { it.copyTo(output) } }
        val chunks=Base64.encodeToString(compressed.toByteArray(),Base64.NO_WRAP).chunked(24000)
        for ((index,chunk) in chunks.withIndex()) sendStatus(0,Bundle().apply {
            putString("luma_file",name);putInt("luma_part",index);putInt("luma_parts",chunks.size);putString("luma_data",chunk)
        })
    }
}
