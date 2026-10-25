package com.example.traductor

import org.junit.Assert.*
import org.junit.Test

class OverlayPlacementTest {
    private val content=ScreenRect(0,40,400,800)
    @Test fun clearUserPositionStaysPut() {
        val bar=ScreenRect(10,50,170,100)
        assertEquals(bar,toolbarPosition(bar,content,listOf(ScreenRect(20,200,380,240)),8))
    }
    @Test fun coveredHeadlineGetsAFreePosition() {
        val bar=ScreenRect(10,100,170,150)
        val text=listOf(ScreenRect(0,110,400,155),ScreenRect(0,205,400,250))
        val moved=requireNotNull(toolbarPosition(bar,content,text,8))
        assertNotEquals(bar,moved);assertTrue(content.contains(moved))
        assertTrue(text.none { ScreenRect(it.left-8,it.top-8,it.right+8,it.bottom+8).intersects(moved) })
    }
    @Test fun fullPageDoesNotInventAFreePosition() {
        assertNull(toolbarPosition(ScreenRect(10,100,170,150),content,listOf(content),8))
    }
    @Test fun textCrossingNavigationBarIsNotComplete() {
        assertFalse(fullyVisibleText(ScreenRect(80,740,300,820),content))
        assertFalse(fullyVisibleText(ScreenRect(-10,200,100,240),content))
        assertFalse(fullyVisibleText(ScreenRect(80,35,300,80),content))
        assertTrue(fullyVisibleText(ScreenRect(80,200,300,240),content))
    }
    @Test fun narrowScreenKeepsTheBarAccessible() {
        val narrow=ScreenRect(12,50,192,600)
        val bar=ScreenRect(-10,100,150,155)
        val moved=requireNotNull(toolbarPosition(bar,narrow,listOf(ScreenRect(12,100,192,200)),6))
        assertTrue(narrow.contains(moved));assertEquals(bar.width,moved.width)
    }
}
