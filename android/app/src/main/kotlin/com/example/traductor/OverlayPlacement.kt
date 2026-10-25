package com.example.traductor

data class ScreenRect(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width get() = right-left
    val height get() = bottom-top
    fun contains(other: ScreenRect) = other.left>=left && other.top>=top && other.right<=right && other.bottom<=bottom
    fun intersects(other: ScreenRect) = left<other.right && right>other.left && top<other.bottom && bottom>other.top
}

fun fullyVisibleText(text: ScreenRect, content: ScreenRect, edge: Int = 2) =
    text.width>0 && text.height>0 && text.left>content.left+edge && text.top>content.top+edge &&
        text.right<content.right-edge && text.bottom<content.bottom-edge

/** Keep a user's clear position; otherwise choose a nearby gap between text. */
fun toolbarPosition(current: ScreenRect, content: ScreenRect, text: List<ScreenRect>, margin: Int): ScreenRect? {
    val width=current.width;val height=current.height
    if(width<=0 || height<=0 || width>content.width || height>content.height)return null
    val obstacles=text.map { ScreenRect(it.left-margin,it.top-margin,it.right+margin,it.bottom+margin) }
    fun clear(rect: ScreenRect) = content.contains(rect) && obstacles.none { it.intersects(rect) }
    if(clear(current))return current
    val points=LinkedHashSet<Pair<Int,Int>>()
    fun add(x: Int,y: Int) { points.add(x.coerceIn(content.left,content.right-width) to y.coerceIn(content.top,content.bottom-height)) }
    for(i in 0..10)for(j in 0..14)add(content.left+(content.width-width)*i/10,content.top+(content.height-height)*j/14)
    for(rect in obstacles) {
        for(x in listOf(current.left,rect.left-width,rect.right))for(y in listOf(current.top,rect.top-height,rect.bottom))add(x,y)
    }
    return points.asSequence().map { (x,y)->ScreenRect(x,y,x+width,y+height) }.filter(::clear)
        .minByOrNull { val dx=(it.left-current.left).toLong();val dy=(it.top-current.top).toLong();dx*dx+dy*dy }
}
