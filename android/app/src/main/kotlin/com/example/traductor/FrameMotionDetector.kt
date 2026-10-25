package com.example.traductor

import kotlin.math.abs

/** Compares small luminance grids. -1 marks our windows and system bars. */
class FrameMotionDetector {
    private var reference: IntArray? = null
    fun reset() { reference = null }
    fun reference(sample: IntArray) { reference = sample.copyOf() }
    fun moved(sample: IntArray): Boolean {
        val previous = reference
        if (previous == null || previous.size != sample.size) { reference(sample); return false }
        var valid = 0; var changed = 0
        for (i in sample.indices) {
            if (sample[i] < 0 || previous[i] < 0) continue
            valid++
            if (abs(sample[i] - previous[i]) > 28) changed++
        }
        // Small clocks, cursors and compression noise must not clear a page.
        return valid > 100 && changed >= maxOf(18, (valid * .025f).toInt())
    }
}

fun normalizeScreenText(text: String): String = text
    .replace(Regex("(?<=\\p{L})-\\s*\\n\\s*(?=\\p{Ll})"), "")
    .replace(Regex("\\s+"), " ").trim()
