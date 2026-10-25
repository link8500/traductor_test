package com.example.traductor;

import android.app.Activity;
import android.app.Instrumentation;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import java.util.Collections;
import java.util.concurrent.TimeUnit;
import kotlin.Pair;
import org.json.JSONArray;
import org.json.JSONObject;

/** Inspect disagreement on real screenshots, using the shipped readers. */
public final class LineSelectionProbe {
    public static void run(Instrumentation instrumentation,Bundle options) {
        TextRecognizer recognizer=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        try(LocalMarian model=new LocalMarian(instrumentation.getTargetContext());
            ParcelFileDescriptor.AutoCloseInputStream input=new ParcelFileDescriptor.AutoCloseInputStream(
                instrumentation.getUiAutomation().executeShellCommand("cat /data/local/tmp/luma-pipeline-screen.png"))) {
            Bitmap image=BitmapFactory.decodeStream(input);
            if(image==null)throw new AssertionError("Missing screen fixture");
            try {
                if("true".equals(options.getString("verify-follow"))) {
                    java.util.List<ComicRegion> fragments=java.util.Arrays.asList(
                        new ComicRegion(new Rect(416,3174,591,3236),"THEN",false,62f,.99f,"THEN",true,true),
                        new ComicRegion(new Rect(582,3244,713,3310),"ME.",false,66f,.99f,"ME.",true,true),
                        new ComicRegion(new Rect(295,3248,577,3305),"FOLLOW",false,57f,.99f,"FOLLOW",true,true));
                    java.util.List<ComicRegion> grouped=ComicText.INSTANCE.mergeParagraphs(fragments);
                    if(grouped.size()!=1||!grouped.get(0).getText().replaceAll("\\s+"," ").equals("THEN FOLLOW ME."))
                        throw new AssertionError("Recorded fragment grouping failed: "+grouped);
                }
                JSONArray lines=new JSONArray();
                Text raw=Tasks.await(recognizer.process(InputImage.fromBitmap(image,0)),30,TimeUnit.SECONDS);
                for(Text.TextBlock block:raw.getTextBlocks())for(Text.Line line:block.getLines()) {
                    Rect bounds=line.getBoundingBox();if(bounds==null)continue;
                    int padding=(int)(bounds.height()*1.1f);
                    Rect crop=new Rect(bounds);crop.inset(-padding,-3);crop.intersect(0,0,image.getWidth(),image.getHeight());
                    Pair<String,Float> local=model.recognizeLine(image,crop);
                    JSONObject row=new JSONObject().put("system",line.getText()).put("system_confidence",line.getConfidence())
                        .put("bounds",new JSONArray(new int[]{bounds.left,bounds.top,bounds.right,bounds.bottom}));
                    // Pair's accessors can be renamed in the optimized target;
                    // Object.toString remains usable without production keep rules.
                    if(local!=null)row.put("local_pair",local.toString());
                    lines.put(row);
                }
                JSONArray detected=new JSONArray();
                for(ComicRegion region:model.findAdditionalText(image,Collections.emptyList()))
                    detected.put(new JSONObject().put("text",region.getText()).put("confidence",region.getConfidence()).put("bounds",region.getBounds().toShortString()));
                JSONArray pipeline=new JSONArray();StringBuilder selected=new StringBuilder();boolean followRecovered=false;
                for(ComicRegion region:ComicOcr.INSTANCE.recognize(recognizer,image,model,()->false)) {
                    JSONObject entry=new JSONObject().put("text",region.getText()).put("system_text",region.getNativeText())
                        .put("confidence",region.getConfidence()).put("local_verified",region.getLineRecognitionVerified());
                    if("true".equals(options.getString("verify-follow"))) {
                        String source=region.getText().replaceAll("\\s+"," ").trim().toUpperCase(java.util.Locale.ROOT);
                        if(source.equals("THEN FOLLOW ME.")) {
                            String translated=model.translate(region.getText());entry.put("translation",translated);
                            followRecovered=true;
                            if(translated.trim().isEmpty())throw new AssertionError("Empty grouped dialogue translation");
                        }
                    }
                    if("true".equals(options.getString("verify-underwater"))) {
                        String source=region.getText().replaceAll("\\s+"," ").toUpperCase(java.util.Locale.ROOT);
                        if(source.contains("A MEAL")) {
                            if(!source.contains("A MEAL UNDERWATER")||!source.contains("WATER GHOSTS")||!source.contains("YANGTZE RIVER"))
                                throw new AssertionError("Underwater source OCR corrupted: "+source);
                            String translated=model.translate(region.getText());entry.put("translation",translated);
                            String lower=translated.toLowerCase(java.util.Locale.ROOT);
                            if(!lower.contains("bajo el agua")||!lower.contains("fantasmas")||lower.contains("nderwater"))
                                throw new AssertionError("Underwater model translation failed: "+translated);
                        }
                    }
                    pipeline.put(entry);
                    selected.append(region.getText()).append(' ');
                }
                if("true".equals(options.getString("verify-follow"))&&!followRecovered)
                    throw new AssertionError("The complete THEN FOLLOW ME balloon was not grouped: "+selected);
                if("true".equals(options.getString("verify-underwater"))&&!selected.toString().contains("UNDERWATER"))
                    throw new AssertionError("Underwater dialogue was not detected");
                if("true".equals(options.getString("verify"))) {
                    String text=selected.toString().replaceAll("\\s+"," ").toUpperCase(java.util.Locale.ROOT);
                    String[] expected={"I'VE WAITED FOR DECADES, BUT TO THINK YOU'D ONLY HAVE ONE CUP", "COME TO THINK OF IT, WHEN I FIRST MET YOU, WE WERE BOTH YOUNG", "TO OBTAIN THE SECRET DEMONIC SOUL"};
                    for(String phrase:expected)if(!text.contains(phrase))throw new AssertionError("Production screen OCR not recovered: "+phrase+" / "+text);
                }
                Bundle result=new Bundle();result.putString("stream",new JSONObject().put("success",true).put("lines",lines).put("db",detected).put("production_pipeline",pipeline).toString());
                instrumentation.finish(Activity.RESULT_OK,result);
            }finally {image.recycle();}
        }catch(Throwable error) {
            Bundle result=new Bundle();result.putString("stream",error.toString());instrumentation.finish(Activity.RESULT_CANCELED,result);
        }finally {recognizer.close();}
    }
}
