package com.example.traductor

import org.junit.Assert.*
import org.junit.Test

class OverlayBackgroundTest {
    private val white=0xffffffff.toInt()
    private val black=0xff000000.toInt()
    @Test fun whiteBalloonIgnoresDarkCornerAndSparseInk() {
        assertEquals(white,OverlayBackground.dominant(80,80,0,0,80,80) { x,y -> if ((x<3 && y<3) || (x%19==0 && y%7==0)) black else white })
    }
    @Test fun darkPanelIgnoresLightCornerAndSparseInk() {
        assertEquals(black,OverlayBackground.dominant(80,80,0,0,80,80) { x,y -> if ((x<3 && y<3) || (x%19==0 && y%7==0)) white else black })
    }
    @Test fun uniformColorPreservesTheActualChannels() {
        val color=0xffc8e0b0.toInt()
        assertEquals(color,OverlayBackground.dominant(80,80,0,0,80,80) { _,_ -> color })
    }
    @Test fun competingBackgroundsKeepTheCallersFallback() {
        assertNull(OverlayBackground.dominant(80,80,0,0,80,80) { x,_ -> if(x<40) black else white })
    }
    @Test fun tinyAndOutsideRegionsDoNotInventAColor() {
        assertNull(OverlayBackground.dominant(80,80,0,0,4,4) { _,_ -> white })
        assertNull(OverlayBackground.dominant(80,80,100,100,120,120) { _,_ -> white })
    }
    @Test fun partiallyClippedRegionUsesValidPixels() {
        assertEquals(white,OverlayBackground.dominant(80,80,-20,-20,40,40) { x,y -> assertTrue(x in 0..79 && y in 0..79); white })
    }
}
