package com.example.traductor

import kotlin.math.abs

/** Close fragments on one baseline, independent of recognition confidence or text. */
fun sameComicLine(a: ScreenRect, aLineHeight: Float, b: ScreenRect, bLineHeight: Float): Boolean {
    val height=minOf(aLineHeight,bLineHeight)
    if(height<=0 || a.width<=0 || b.width<=0 || a.height<=0 || b.height<=0)return false
    if(maxOf(aLineHeight,bLineHeight)>height*1.6f || a.height>aLineHeight*1.5f || b.height>bLineHeight*1.5f)return false
    val overlap=minOf(a.bottom,b.bottom)-maxOf(a.top,b.top)
    val gap=maxOf(a.left,b.left)-minOf(a.right,b.right)
    return overlap>=height*.6f && abs((a.top+a.bottom-b.top-b.bottom)/2f)<=height*.4f &&
        gap>=0 && gap<=height*.65f
}
