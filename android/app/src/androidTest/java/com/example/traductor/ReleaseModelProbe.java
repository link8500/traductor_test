package com.example.traductor;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Locale;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONArray;
import org.json.JSONObject;

/** Runs through kept public JNI wrappers on the actual R8-optimized APK. */
public final class ReleaseModelProbe {
    public static void run(Instrumentation instrumentation, Bundle options) {
        long started=System.nanoTime();
        try(LocalMarian model=new LocalMarian(instrumentation.getTargetContext())) {
            String fixture=new String(instrumentation.getContext().getAssets().open("ocr-normalization-cases.json").readAllBytes(),StandardCharsets.UTF_8);
            JSONArray repairs=new JSONArray(fixture);int checked=0;
            for(int i=0;i<repairs.length();i++) {
                JSONObject item=repairs.getJSONObject(i);JSONArray fragments=item.optJSONArray("target_any");
                if(fragments==null)continue;
                String result=model.translate(item.getString("source")).toLowerCase(Locale.ROOT);boolean found=false;
                for(int j=0;j<fragments.length();j++)if(result.contains(fragments.getString(j).toLowerCase(Locale.ROOT)))found=true;
                if(!found)throw new AssertionError("Native release translation failed: "+result);
                checked++;
            }
            File inputs=new File(instrumentation.getTargetContext().getFilesDir(),"comic-quality/model-input.json");
            String sampleText=inputs.isFile()?new String(Files.readAllBytes(inputs.toPath()),StandardCharsets.UTF_8):
                new String(instrumentation.getContext().getAssets().open("model-smoke-input.json").readAllBytes(),StandardCharsets.UTF_8);
            JSONArray samples=new JSONArray(sampleText);
            for(int i=0;i<samples.length();i++)model.translate(samples.getJSONObject(i).getString("source"));
            int[] colours={Color.BLACK,Color.RED,Color.BLUE,Color.GREEN,Color.YELLOW,Color.WHITE,Color.RED,Color.BLUE,Color.YELLOW};
            float[] angles={0,0,0,0,0,0,-14,18,-10};int colourCases=0;
            for(int i=0;i<colours.length;i++) {
                Bitmap image=Bitmap.createBitmap(700,360,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(image);
                canvas.drawColor(i==4||i==5||i==8?Color.rgb(24,33,50):Color.WHITE);
                canvas.rotate(angles[i],350,180);
                Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);paint.setTextSize(36);paint.setTypeface(Typeface.DEFAULT_BOLD);paint.setColor(colours[i]);
                if(i==8){paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(5);paint.setColor(Color.BLACK);canvas.drawText("THE ANCIENT SWORD",140,190,paint);paint.setStyle(Paint.Style.FILL);paint.setColor(colours[i]);}
                canvas.drawText("THE ANCIENT SWORD",140,190,paint);
                StringBuilder recognized=new StringBuilder();
                for(ComicRegion region:model.findAdditionalText(image,Collections.emptyList()))recognized.append(region.getText()).append(' ');
                if(!recognized.toString().toUpperCase(Locale.ROOT).contains("THE ANCIENT SWORD"))throw new AssertionError("Colour/rotation detection "+i+": "+recognized);
                if(i==0&&!model.findAdditionalText(image,Collections.singletonList(new Rect(0,0,700,360))).isEmpty())throw new AssertionError("Duplicate text was added");
                image.recycle();colourCases++;
            }
            Bitmap blank=Bitmap.createBitmap(700,360,Bitmap.Config.ARGB_8888);blank.eraseColor(Color.WHITE);
            if(!model.findAdditionalText(blank,Collections.emptyList()).isEmpty())throw new AssertionError("Blank image detected as text");blank.recycle();
            boolean styledScreen=false;
            if("true".equals(options.getString("styled"))) {
                try(ParcelFileDescriptor.AutoCloseInputStream input=new ParcelFileDescriptor.AutoCloseInputStream(
                    instrumentation.getUiAutomation().executeShellCommand("cat /data/local/tmp/luma-style-screen.png"))) {
                    Bitmap image=BitmapFactory.decodeStream(input);
                    if(image==null)throw new AssertionError("Missing styled screen fixture");
                    boolean recovered=false;
                    try {
                        for(ComicRegion region:model.findAdditionalText(image,Collections.emptyList()))
                            if(region.getText().equalsIgnoreCase("FOR REVENGE"))recovered=true;
                    }finally {image.recycle();}
                    if(!recovered)throw new AssertionError("Tall red lettering was not recovered");
                    styledScreen=true;
                }
            }
            int comicLineCases=0;
            if("true".equals(options.getString("handwriting"))) {
                String[][] expected={{"I'VE WAITED FOR","ONLY HAVE ONE CUP"},{"COME TO THINK","BOTH YOUNG"},{"TO OBTAIN THE SECRET","DEMONIC SOUL"}};
                for(int i=0;i<expected.length;i++) {
                    try(ParcelFileDescriptor.AutoCloseInputStream input=new ParcelFileDescriptor.AutoCloseInputStream(
                        instrumentation.getUiAutomation().executeShellCommand("cat /data/local/tmp/luma-comic-line-"+i+".png"))) {
                        Bitmap image=BitmapFactory.decodeStream(input);
                        if(image==null)throw new AssertionError("Missing real comic lettering fixture "+i);
                        StringBuilder text=new StringBuilder();
                        try { for(ComicRegion region:model.findAdditionalText(image,Collections.emptyList()))text.append(region.getText()).append(' '); }
                        finally {image.recycle();}
                        String recognized=text.toString().replaceAll("\\s+"," ").toUpperCase(Locale.ROOT);
                        for(String phrase:expected[i])if(!recognized.contains(phrase))throw new AssertionError("Real comic lettering not recovered: "+i+" / "+phrase+" / "+recognized);
                        comicLineCases++;
                    }
                }
            }
            AtomicBoolean cancelled=new AtomicBoolean(false);
            Thread worker=new Thread(()-> {try {model.translate("This is a long paragraph about survival at an academy. ".repeat(30));}
                catch(IllegalStateException expected){cancelled.set(true);}});
            worker.start();Thread.sleep(150);model.cancel();worker.join(5000);
            if(worker.isAlive()||!cancelled.get())throw new AssertionError("Release decoder cancellation failed");
            if(!model.translate("Hello world").toLowerCase(Locale.ROOT).contains("hola"))throw new AssertionError("Release decoder recovery failed");
            JSONObject report=new JSONObject().put("success",true).put("repair_and_domain_cases",checked).put("samples",samples.length())
                .put("cancellation",true).put("recovery",true).put("r8_optimized_apk",true).put("milliseconds",(System.nanoTime()-started)/1_000_000);
            report.put("colour_and_rotation_cases",colourCases).put("comic_line_fixtures",comicLineCases).put("duplicate_suppression",true).put("blank_image",true);
            report.put("styled_screen_recovery",styledScreen)
                .put("version_code",instrumentation.getTargetContext().getPackageManager().getPackageInfo(instrumentation.getTargetContext().getPackageName(),0).getLongVersionCode())
                .put("abi",android.os.Build.SUPPORTED_ABIS[0]);
            Bundle result=new Bundle();result.putString("stream",report.toString());instrumentation.finish(Activity.RESULT_OK,result);
        }catch(Throwable error) {
            Bundle result=new Bundle();result.putString("stream",error.toString());instrumentation.finish(Activity.RESULT_CANCELED,result);
        }
    }
}
