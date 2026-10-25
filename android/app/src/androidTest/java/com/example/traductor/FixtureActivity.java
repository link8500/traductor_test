package com.example.traductor;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;

/** Standalone fixture reader in the separate, disposable test APK. */
public final class FixtureActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String url=getIntent().getStringExtra("url");
        if(url==null)url="http://127.0.0.1:8765/fixture.html";
        if(!url.startsWith("http://127.0.0.1:8765/"))throw new IllegalArgumentException("Local fixtures only");
        WebView reader=new WebView(this);
        reader.getSettings().setJavaScriptEnabled(false);
        setContentView(reader);
        reader.loadUrl(url);
    }
}
