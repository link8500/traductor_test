package com.example.traductor

import org.junit.Assert.*
import org.junit.Test

class ComicLineLayoutTest {
    @Test fun restoresFollowMeDespiteDifferentTopCoordinates() {
        assertTrue(sameComicLine(ScreenRect(582,3244,713,3310),66f,ScreenRect(295,3248,577,3305),57f))
        assertTrue(sameComicLine(ScreenRect(295,3248,577,3305),57f,ScreenRect(582,3244,713,3310),66f))
    }
    @Test fun separateLinesRemainSeparateUntilParagraphGrouping() {
        assertFalse(sameComicLine(ScreenRect(416,3174,591,3236),62f,ScreenRect(295,3244,713,3310),66f))
    }
    @Test fun separateColumnsAndControlsDoNotRejoin() {
        assertFalse(sameComicLine(ScreenRect(0,0,80,30),30f,ScreenRect(120,0,200,30),30f))
    }
    @Test fun overlappingDuplicateDetectionsDoNotCreateRepeatedWords() {
        assertFalse(sameComicLine(ScreenRect(0,0,100,30),30f,ScreenRect(50,0,150,30),30f))
    }
    @Test fun multilineBlocksAndDifferentFontSizesRemainSeparate() {
        assertFalse(sameComicLine(ScreenRect(0,0,100,90),30f,ScreenRect(105,0,140,30),30f))
        assertFalse(sameComicLine(ScreenRect(0,0,100,60),60f,ScreenRect(105,20,140,40),20f))
    }
    @Test fun lineGroupingWorksAtPhoneAndDesktopScales() {
        for(scale in listOf(1,2,3)) {
            assertTrue(sameComicLine(ScreenRect(0,2*scale,100*scale,30*scale),28f*scale,
                ScreenRect(105*scale,0,150*scale,32*scale),32f*scale))
        }
    }
}
