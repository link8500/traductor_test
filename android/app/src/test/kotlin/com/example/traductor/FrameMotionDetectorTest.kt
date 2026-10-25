package com.example.traductor

import org.junit.Assert.*
import org.junit.Test

class FrameMotionDetectorTest {
    @Test fun ignoresNoiseAndSmallClockChanges() {
        val detector = FrameMotionDetector()
        detector.reference(IntArray(6144) { 120 })
        assertFalse(detector.moved(IntArray(6144) { 126 }))
        assertFalse(detector.moved(IntArray(6144) { if (it < 12) 255 else 120 }))
    }
    @Test fun detectsPageMovementAndKeepsTheReferenceForSlowDrags() {
        val detector = FrameMotionDetector()
        detector.reference(IntArray(6144) { 120 })
        assertFalse(detector.moved(IntArray(6144) { if (it < 60) 200 else 120 }))
        assertTrue(detector.moved(IntArray(6144) { if (it < 600) 200 else 120 }))
    }
    @Test fun ignoresTranslatedTextAndToolbarMasks() {
        val detector = FrameMotionDetector()
        detector.reference(IntArray(6144) { 120 })
        assertFalse(detector.moved(IntArray(6144) { if (it < 3000) -1 else 120 }))
    }
    @Test fun draggingToolbarCanResetTheReference() {
        val detector = FrameMotionDetector()
        detector.reference(IntArray(6144) { 120 })
        detector.reset()
        assertFalse(detector.moved(IntArray(6144) { 220 }))
        assertFalse(detector.moved(IntArray(6144) { 220 }))
    }
    @Test fun joinsWrappedParagraphsWithoutLosingPunctuation() {
        assertEquals("SUBCONSCIOUSLY, I THOUGHT MY LIFE WASN'T PRECIOUS BECAUSE I'M A REGRESSOR.",
            normalizeScreenText("SUBCONSCIOUSLY,\nI THOUGHT MY LIFE WASN'T\n PRECIOUS BECAUSE\nI'M A REGRESSOR."))
        assertEquals("translation works", normalizeScreenText("trans-\nlation   works"))
    }
}
