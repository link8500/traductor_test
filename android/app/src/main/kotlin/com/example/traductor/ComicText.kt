package com.example.traductor

import android.graphics.Rect
import com.google.mlkit.vision.text.Text

data class ComicRegion(val bounds: Rect, val text: String, val centered: Boolean = false,
    val lineHeight: Float = bounds.height().toFloat() / text.lines().size.coerceAtLeast(1), val confidence: Float = 0f,
    val nativeText: String = text, val additionalDetection: Boolean = false, val lineRecognitionVerified: Boolean = false)

/** Shared by the overlay and the corpus benchmark: no separate test OCR path. */
object ComicText {
    fun regions(recognized: Text): List<ComicRegion> {
        val regions = ArrayList<ComicRegion>()
        for (block in recognized.textBlocks) {
            val parts = ArrayList<ComicRegion>()
            var separatedControls = false
            for (line in block.lines) {
                val elements = line.elements.filter { it.boundingBox != null }.sortedBy { it.boundingBox!!.left }
                if (elements.isEmpty()) continue
                val widths = elements.map { it.boundingBox!!.width().toFloat() / it.text.length.coerceAtLeast(1) }.sorted()
                val limit = maxOf((line.boundingBox?.height() ?: 20) * .8f, widths[widths.size/2]*2f)
                var bounds = Rect(elements.first().boundingBox!!)
                val words = StringBuilder(elements.first().text)
                for (element in elements.drop(1)) {
                    val next = element.boundingBox!!
                    if (next.left-bounds.right > limit) {
                        parts.add(ComicRegion(Rect(bounds),words.toString(),confidence=line.confidence)); bounds=Rect(next); words.clear(); separatedControls=true
                    } else { bounds.union(next); words.append(' ') }
                    words.append(element.text)
                }
                parts.add(ComicRegion(bounds,words.toString(),confidence=line.confidence))
            }
            if (separatedControls) regions.addAll(parts)
            else block.boundingBox?.let { bounds ->
                val centers=block.lines.mapNotNull { it.boundingBox?.exactCenterX() }
                val centered=centers.size>1 && centers.maxOrNull()!!-centers.minOrNull()!!<bounds.width()*.14f
                val height = block.lines.mapNotNull { it.boundingBox?.height()?.toFloat() }.average().toFloat()
                val confidence=block.lines.map { it.confidence }.average().toFloat()
                regions.add(ComicRegion(Rect(bounds),block.text.trim(),centered,height,confidence))
            }
        }
        return mergeParagraphs(regions)
    }

    /** OCR often splits the short first/last line from the rest of one balloon. */
    fun mergeParagraphs(input: List<ComicRegion>): List<ComicRegion> {
        val regions = input.sortedWith(compareBy<ComicRegion> { it.bounds.top }.thenBy { it.bounds.left }).toMutableList()
        // DB can return the right-hand word a few pixels above the left one.
        // Rebuild that baseline before trying to join successive text lines.
        var rowIndex=0
        while(rowIndex<regions.size) {
            val first=regions[rowIndex]
            val nextIndex=(rowIndex+1 until regions.size).firstOrNull { candidate ->
                val second=regions[candidate]
                fun box(r: ComicRegion)=ScreenRect(r.bounds.left,r.bounds.top,r.bounds.right,r.bounds.bottom)
                !first.text.contains('\n') && !second.text.contains('\n') &&
                    first.text.length+second.text.length<1500 &&
                    sameComicLine(box(first),first.lineHeight,box(second),second.lineHeight)
            }
            if(nextIndex==null) { rowIndex++;continue }
            val second=regions.removeAt(nextIndex)
            val (left,right)=if(first.bounds.left<=second.bounds.left)first to second else second to first
            val total=(left.text.length+right.text.length).coerceAtLeast(1)
            regions[rowIndex]=ComicRegion(Rect(left.bounds).apply { union(right.bounds) },left.text+" "+right.text,
                false,maxOf(left.lineHeight,right.lineHeight),
                (left.confidence*left.text.length+right.confidence*right.text.length)/total,
                left.nativeText+" "+right.nativeText,left.additionalDetection||right.additionalDetection,
                left.lineRecognitionVerified&&right.lineRecognitionVerified)
        }
        regions.sortWith(compareBy<ComicRegion> { it.bounds.top }.thenBy { it.bounds.left })
        var index = 0
        while (index < regions.size) {
            val first = regions[index]
            val nextIndex = (index+1 until regions.size).firstOrNull { candidate ->
                val second = regions[candidate]
                val a=first.bounds; val b=second.bounds
                val height=minOf(first.lineHeight,second.lineHeight)
                val gap=b.top-a.bottom
                val overlap=minOf(a.right,b.right)-maxOf(a.left,b.left)
                val aligned=kotlin.math.abs(a.exactCenterX()-b.exactCenterX())<maxOf(a.width(),b.width())*.16f ||
                    kotlin.math.abs(a.left-b.left)<height*.45f
                // OCR measures the ink height, which is shorter than the
                // font's line box. Uppercase browser/comic lines can have
                // nearly one ink-height of whitespace inside one paragraph.
                gap>=-height*.12f && gap<=height && height>0 &&
                    maxOf(first.lineHeight,second.lineHeight)<height*1.6f &&
                    overlap>minOf(a.width(),b.width())*.45f && aligned &&
                    // A region between the lines in the same column prevents merging.
                    (index+1 until candidate).none { middle ->
                        val r=regions[middle].bounds
                        r.top>=a.bottom && r.bottom<=b.top && r.right>minOf(a.left,b.left) && r.left<maxOf(a.right,b.right)
                    }
            }
            if (nextIndex == null) { index++; continue }
            val second=regions.removeAt(nextIndex)
            val bounds=Rect(first.bounds).apply { union(second.bounds) }
            val centered=kotlin.math.abs(first.bounds.exactCenterX()-second.bounds.exactCenterX())<bounds.width()*.16f
            regions[index]=ComicRegion(bounds,first.text+"\n"+second.text,centered,(first.lineHeight+second.lineHeight)/2,
                (first.confidence*first.text.length+second.confidence*second.text.length)/(first.text.length+second.text.length),
                first.nativeText+"\n"+second.nativeText,first.additionalDetection||second.additionalDetection)
        }
        return regions
    }
}
