package com.example.traductor;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import java.nio.FloatBuffer;
import java.util.Arrays;
import java.util.Collections;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

/** Small reproducer for ARM int4 loading; no screen capture or user data. */
public final class ArmKernelProbe extends Instrumentation {
    private Bundle arguments;
    @Override public void onCreate(Bundle args) { super.onCreate(args);arguments=args;start(); }
    @Override public void onStart() { run(this,arguments); }
    public static void run(Instrumentation instrumentation,Bundle arguments) {
        String mode=arguments.getString("probe","level4");
        if(mode.equals("release-model")) { ReleaseModelProbe.run(instrumentation,arguments);return; }
        Bundle status=new Bundle();status.putString("stream","Loading int4 kernel probe: "+mode);instrumentation.sendStatus(0,status);
        long started=System.nanoTime();
        try {
            OrtEnvironment env=OrtEnvironment.getEnvironment();
            boolean full=mode.startsWith("decoder") || mode.startsWith("encoder");
            String asset=full?"flutter_assets/assets/models/opus-en-es/"+(mode.startsWith("encoder")?"encoder":"decoder")+".onnx":
                mode.startsWith("subgraph")?"arm-int4-"+mode.replace("-no-prepack","")+".onnx":mode.equals("level0")?"arm-int4-level0.onnx":"arm-int4-level4.onnx";
            File file=null;
            byte[] model=null;
            if(full) {
                file=new File(instrumentation.getTargetContext().getCacheDir(),"arm-kernel-probe.onnx");
                try(InputStream input=instrumentation.getTargetContext().getAssets().open(asset);FileOutputStream output=new FileOutputStream(file)) {
                    byte[] buffer=new byte[65536];int count;
                    while((count=input.read(buffer))!=-1)output.write(buffer,0,count);
                }
            } else model=instrumentation.getContext().getAssets().open(asset).readAllBytes();
            try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()) {
                options.setIntraOpNumThreads(2);
                if(mode.contains("no-prepack"))options.addConfigEntry("session.disable_prepacking","1");
                if(mode.contains("basic"))options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.BASIC_OPT);
                try(OrtSession session=full?env.createSession(file.getAbsolutePath(),options):env.createSession(model,options)) {
                    if(!full) {
                    float[] input=new float[1024];Arrays.fill(input,1f);
                    try(OnnxTensor tensor=OnnxTensor.createTensor(env,FloatBuffer.wrap(input),new long[]{1,1024});
                        OrtSession.Result result=session.run(Collections.singletonMap("A",tensor))) {
                        float[][] output=(float[][])result.get(0).getValue();
                        for(float value:output[0])if(!Float.isFinite(value)||Math.abs(value-64f)>.01f)throw new AssertionError("Incorrect int4 output: "+value);
                    }
                    }
                }
            }
            if(file!=null)file.delete();
            Bundle done=new Bundle();done.putString("stream","PASS "+mode+(full?" load":" load + inference")+" in "+(System.nanoTime()-started)/1_000_000+" ms");
            instrumentation.finish(Activity.RESULT_OK,done);
        } catch(Throwable error) {
            Bundle failed=new Bundle();failed.putString("stream",error.toString());instrumentation.finish(Activity.RESULT_CANCELED,failed);
        }
    }
}
