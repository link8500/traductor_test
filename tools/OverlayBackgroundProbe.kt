package com.example.traductor

import java.io.File

fun main(args: Array<String>) {
    val output=File(args[1]).bufferedWriter()
    output.use { writer ->
        for (line in File(args[0]).readLines()) {
            val fields=line.split('\t'); val bytes=File(fields[1]).readBytes()
            val width=fields[2].toInt(); val height=fields[3].toInt()
            val color=OverlayBackground.dominant(width,height,fields[4].toInt(),fields[5].toInt(),fields[6].toInt(),fields[7].toInt()) { x,y ->
                val at=(y*width+x)*4
                (255 shl 24) or ((bytes[at+2].toInt() and 255) shl 16) or ((bytes[at+1].toInt() and 255) shl 8) or (bytes[at].toInt() and 255)
            }
            writer.write(fields[0]+"\t"+(color?.let { Integer.toHexString(it) } ?: "none")+"\n")
        }
    }
}
