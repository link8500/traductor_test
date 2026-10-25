package com.example.traductor

import kotlin.math.roundToInt

/** Rendering only: this must never change OCR grouping or the model input. */
internal object OverlayBackground {
    fun dominant(width: Int, height: Int, left: Int, top: Int, right: Int, bottom: Int,
                 pixel: (Int, Int) -> Int): Int? {
        if (width < 1 || height < 1) return null
        val l=left.coerceIn(0,width); val r=right.coerceIn(0,width)
        val t=top.coerceIn(0,height); val b=bottom.coerceIn(0,height)
        if (r-l < 8 || b-t < 8) return null
        fun key(color: Int) = (((color ushr 16) and 255)/32)*64 + (((color ushr 8) and 255)/32)*8 + (color and 255)/32
        val samples=IntArray(17*13); val counts=IntArray(512)
        for (row in 0 until 13) for (column in 0 until 17) {
            val x=(l+(r-l-1)*(column+.5)/17).roundToInt()
            val y=(t+(b-t-1)*(row+.5)/13).roundToInt()
            val color=pixel(x,y); samples[row*17+column]=color; counts[key(color)]++
        }
        val selected=counts.indices.maxByOrNull { counts[it] } ?: return null
        if (counts[selected]*4 < samples.size*3) return null
        val matching=samples.filter { key(it)==selected }
        fun channel(shift: Int) = matching.map { (it ushr shift) and 255 }.sorted()[matching.size/2]
        return (255 shl 24) or (channel(16) shl 16) or (channel(8) shl 8) or channel(0)
    }
}
