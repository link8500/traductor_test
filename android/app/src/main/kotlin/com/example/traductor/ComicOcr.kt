package com.example.traductor

import android.graphics.Bitmap
import android.graphics.Rect
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Paint
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognizer
import java.util.concurrent.TimeUnit

/** Retry uncertain/small lettering at a second scale, without inventing words. */
object ComicOcr {
    fun recognize(recognizer: TextRecognizer, bitmap: Bitmap, local: LocalMarian? = null, cancelled: () -> Boolean = { false }): List<ComicRegion> {
        val first=Tasks.await(recognizer.process(InputImage.fromBitmap(bitmap,0)),30,TimeUnit.SECONDS)
        val regions=ComicText.regions(first).map { region ->
            if(local==null||cancelled())return@map region
            val lines=first.textBlocks.flatMap { it.lines }.filter { line ->
                val bounds=line.boundingBox
                bounds!=null&&region.bounds.contains(bounds.centerX(),bounds.centerY())
            }
            if(lines.isEmpty())return@map region
            val recognized=lines.sortedBy { it.boundingBox!!.top }.map lineRead@ { line ->
                if(cancelled())return@lineRead Triple(line.text,line.confidence,false)
                val bounds=line.boundingBox!!;val padding=(bounds.height()*1.1f).toInt()
                val crop=Rect(bounds).apply { inset(-padding,-3);intersect(0,0,bitmap.width,bitmap.height) }
                val candidate=local.recognizeLineWithHint(bitmap,crop,if(line.confidence>=.65f)line.text else "")
                if(candidate!=null&&((candidate.systemAgreement&&candidate.confidence>=.75f)||candidate.confidence>=maxOf(.85f,line.confidence-.025f))&&
                    candidate.text.length>=line.text.length*.7&&candidate.text.length<=line.text.length*2.3+8) {
                    val letters=line.text.filter { it.isLetter() }
                    Triple(if(letters.isNotEmpty()&&letters.count { it.isUpperCase() }>=letters.length*.75)candidate.text.uppercase() else candidate.text,candidate.confidence,true)
                } else Triple(line.text,line.confidence,false)
            }
            region.copy(text=recognized.joinToString("\n") { it.first },confidence=recognized.map { it.second }.average().toFloat(),lineRecognitionVerified=recognized.all { it.third })
        }
        val refined=regions.map { region ->
            if (cancelled()||region.lineRecognitionVerified) return@map region
            val corners=listOf(region.bounds.left to region.bounds.top,region.bounds.right to region.bounds.top,
                region.bounds.left to region.bounds.bottom,region.bounds.right to region.bounds.bottom)
                .map { (x,y) -> bitmap.getPixel(x.coerceIn(0,bitmap.width-1),y.coerceIn(0,bitmap.height-1)) }
            val dark=corners.count { Color.red(it)+Color.green(it)+Color.blue(it)<330 }>=3
            val uncertain=region.confidence in .01f.. .91f || region.lineHeight<26 || dark
            if (!uncertain || region.text.count { it.isLetter() }<5) return@map region
            val rect=Rect(region.bounds).apply { inset(-8,-8); intersect(0,0,bitmap.width,bitmap.height) }
            if (rect.width()<4 || rect.height()<4 || rect.width()*rect.height()>1_200_000) return@map region
            val crop=Bitmap.createBitmap(bitmap,rect.left,rect.top,rect.width(),rect.height())
            val scale=minOf(2f,1800f/rect.width()).coerceAtLeast(1f)
            val enlarged=Bitmap.createBitmap((crop.width*scale).toInt(),(crop.height*scale).toInt(),Bitmap.Config.ARGB_8888)
            val paint=Paint(Paint.FILTER_BITMAP_FLAG)
            if (dark) paint.colorFilter=ColorMatrixColorFilter(ColorMatrix(floatArrayOf(
                -.299f,-.587f,-.114f,0f,255f, -.299f,-.587f,-.114f,0f,255f,
                -.299f,-.587f,-.114f,0f,255f, 0f,0f,0f,1f,0f)))
            Canvas(enlarged).drawBitmap(crop,null,Rect(0,0,enlarged.width,enlarged.height),paint)
            try {
                if (cancelled()) return@map region
                val retry=ComicText.regions(Tasks.await(recognizer.process(InputImage.fromBitmap(enlarged,0)),20,TimeUnit.SECONDS))
                val text=retry.sortedBy { it.bounds.top }.joinToString("\n") { it.text }
                val confidence=if (retry.isEmpty()) 0f else retry.map { it.confidence }.average().toFloat()
                if (confidence>region.confidence+.025f && text.length>=region.text.length*.75 && text.length<=region.text.length*1.25)
                    region.copy(text=text,confidence=confidence) else region
            } finally {
                if (enlarged !== crop) enlarged.recycle()
                if (crop !== bitmap) crop.recycle()
            }
        }
        if(local==null||cancelled())return refined
        val known=first.textBlocks.flatMap { it.lines }.mapNotNull { it.boundingBox }
        val additional=local.findAdditionalText(bitmap,known)
        if(cancelled())return emptyList()
        return ComicText.mergeParagraphs(refined+additional)
    }
}
