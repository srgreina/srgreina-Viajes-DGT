package es.srgreina.viajesdgt;

import android.Manifest;
import android.app.UiModeManager;
import android.content.Context;
import android.content.res.Configuration;
import android.media.AudioAttributes;
import android.media.AudioDeviceInfo;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Voz de la app en el coche.
 *  - "hfp": por el canal de manos libres (como una llamada): el equipo del coche silencia la radio mientras habla.
 *  - "auto": con Android Auto (modo coche), por su canal de navegación, como Google Maps; sin él, como "hfp".
 *  - "duck": por el audio normal (Bluetooth A2DP o altavoz) como navegación, pausando la música del propio móvil.
 *  - "speaker": por el altavoz del móvil aunque haya Bluetooth conectado.
 * Si el manos libres no está disponible o no abre en 4 s, se usa "duck" y se informa en la respuesta.
 * La respuesta de speak trae route: "nav" (Android Auto), "hfp", "duck" o "speaker".
 */
@CapacitorPlugin(
    name = "VozCoche",
    permissions = { @Permission(strings = { Manifest.permission.BLUETOOTH_CONNECT }, alias = "bt") }
)
public class VozCochePlugin extends Plugin {

    private static final int IDLE = 0, OPENING = 1, OPEN = 2;
    private static final long SCO_TIMEOUT_MS = 4000, SCO_SETTLE_MS = 600, RELEASE_DELAY_MS = 1200;

    private final Handler main = new Handler(Looper.getMainLooper());
    private AudioManager am;
    private TextToSpeech tts;
    private boolean ttsReady = false;

    private int state = IDLE;
    private String route = null;          // canal realmente usado en la ráfaga actual
    private int pendingUtterances = 0;
    private long seq = 0;                 // invalida esperas de apertura pendientes
    private long utt = 0;
    private final List<Object[]> queue = new ArrayList<>(); // {texto, PluginCall}
    private Object focusRequest = null;   // AudioFocusRequest (API 26+)
    private final AudioManager.OnAudioFocusChangeListener focusListener = (c) -> { };
    private final Runnable releaseTask = this::release;

    @Override
    public void load() {
        am = (AudioManager) getContext().getSystemService(Context.AUDIO_SERVICE);
        tts = new TextToSpeech(getContext(), (status) -> main.post(() -> {
            ttsReady = status == TextToSpeech.SUCCESS;
            if (ttsReady) tts.setLanguage(new Locale("es", "ES"));
            pump();
        }));
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { }
            @Override public void onDone(String id) { main.post(() -> finished()); }
            @Override public void onError(String id) { main.post(() -> finished()); }
        });
    }

    @PluginMethod
    public void speak(PluginCall call) {
        String text = call.getString("text", "");
        String mode = call.getString("mode", "hfp");
        if (text == null || text.isEmpty()) { call.reject("Sin texto"); return; }
        main.post(() -> {
            main.removeCallbacks(releaseTask);
            queue.add(new Object[] { text, call });
            if (state == IDLE) open(mode);
            else pump();
        });
    }

    @PluginMethod
    public void stop(PluginCall call) {
        main.post(() -> {
            if (tts != null) tts.stop();
            for (Object[] q : queue) ((PluginCall) q[1]).reject("Cancelado");
            queue.clear();
            pendingUtterances = 0;
            release();
            call.resolve();
        });
    }

    /** ¿Hay un manos libres Bluetooth conectado ahora mismo? */
    @PluginMethod
    public void status(PluginCall call) {
        JSObject r = new JSObject();
        r.put("hfp", hasScoDevice());
        r.put("car", inCarMode());
        call.resolve(r);
    }

    // ---------------------------------------------------------------------------------------------

    /** Android Auto pone el móvil en modo coche mientras está conectado */
    private boolean inCarMode() {
        UiModeManager um = (UiModeManager) getContext().getSystemService(Context.UI_MODE_SERVICE);
        return um != null && um.getCurrentModeType() == Configuration.UI_MODE_TYPE_CAR;
    }

    private boolean hasScoDevice() {
        if (Build.VERSION.SDK_INT >= 31) {
            for (AudioDeviceInfo d : am.getAvailableCommunicationDevices())
                if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) return true;
            return false;
        }
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_OUTPUTS))
            if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) return true;
        return false;
    }

    private boolean scoActive() {
        if (Build.VERSION.SDK_INT >= 31) {
            AudioDeviceInfo d = am.getCommunicationDevice();
            return d != null && d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO;
        }
        return am.isBluetoothScoOn();
    }

    private void open(String mode) {
        state = OPENING;
        if ("auto".equals(mode)) {
            if (inCarMode()) { nav("nav"); return; }
            mode = "hfp";
        }
        if ("hfp".equals(mode) && hasScoDevice()) {
            route = "hfp";
            requestFocus(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT, AudioAttributes.USAGE_VOICE_COMMUNICATION);
            am.setMode(AudioManager.MODE_IN_COMMUNICATION);
            boolean ok = true;
            if (Build.VERSION.SDK_INT >= 31) {
                ok = false;
                for (AudioDeviceInfo d : am.getAvailableCommunicationDevices())
                    if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) { ok = am.setCommunicationDevice(d); break; }
            } else {
                try { am.startBluetoothSco(); am.setBluetoothScoOn(true); } catch (Exception e) { ok = false; }
            }
            if (!ok) { fallback(); return; }
            final long started = System.currentTimeMillis();
            final long mySeq = ++seq;
            main.post(new Runnable() {
                @Override public void run() {
                    if (mySeq != seq || state != OPENING) return;
                    if (scoActive()) { main.postDelayed(() -> { if (mySeq == seq && state == OPENING) { state = OPEN; pump(); } }, SCO_SETTLE_MS); return; }
                    if (System.currentTimeMillis() - started > SCO_TIMEOUT_MS) { fallback(); return; }
                    main.postDelayed(this, 150);
                }
            });
            return;
        }
        if ("speaker".equals(mode)) {
            route = "speaker";
            requestFocus(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK, AudioAttributes.USAGE_VOICE_COMMUNICATION);
            am.setMode(AudioManager.MODE_IN_COMMUNICATION);
            boolean ok = false;
            if (Build.VERSION.SDK_INT >= 31) {
                for (AudioDeviceInfo d : am.getAvailableCommunicationDevices())
                    if (d.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) { ok = am.setCommunicationDevice(d); break; }
            } else {
                am.setSpeakerphoneOn(true);
                ok = true;
            }
            if (!ok) { fallback(); return; }
            state = OPEN;
            pump();
            return;
        }
        fallback();
    }

    /** Audio normal como indicación de navegación, pausando la música del móvil mientras habla. */
    private void fallback() { nav("duck"); }

    private void nav(String r) {
        resetRouting();
        route = r;
        requestFocus(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT, AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE);
        state = OPEN;
        pump();
    }

    private void pump() {
        if (state != OPEN || !ttsReady) return;
        boolean navRoute = "duck".equals(route) || "nav".equals(route);
        int usage = navRoute ? AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE : AudioAttributes.USAGE_VOICE_COMMUNICATION;
        tts.setAudioAttributes(new AudioAttributes.Builder()
            .setUsage(usage).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
        while (!queue.isEmpty()) {
            Object[] q = queue.remove(0);
            Bundle p = new Bundle();
            p.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f); // los atributos de audio deciden el canal
            pendingUtterances++;
            int res = tts.speak((String) q[0], TextToSpeech.QUEUE_ADD, p, "vc" + (++utt));
            PluginCall call = (PluginCall) q[1];
            if (res == TextToSpeech.SUCCESS) {
                JSObject r = new JSObject();
                r.put("route", route);
                call.resolve(r);
            } else {
                pendingUtterances--;
                call.reject("No se pudo hablar");
            }
        }
        if (pendingUtterances == 0) main.postDelayed(releaseTask, RELEASE_DELAY_MS);
    }

    private void finished() {
        if (pendingUtterances > 0) pendingUtterances--;
        if (pendingUtterances == 0 && queue.isEmpty()) {
            main.removeCallbacks(releaseTask);
            main.postDelayed(releaseTask, RELEASE_DELAY_MS); // pequeña espera por si llega otro aviso seguido
        }
    }

    private void release() {
        if (pendingUtterances > 0 || !queue.isEmpty()) return;
        seq++;
        resetRouting();
        abandonFocus();
        state = IDLE;
        route = null;
    }

    private void resetRouting() {
        try {
            if (Build.VERSION.SDK_INT >= 31) am.clearCommunicationDevice();
            else { am.setBluetoothScoOn(false); am.stopBluetoothSco(); am.setSpeakerphoneOn(false); }
        } catch (Exception ignored) { }
        am.setMode(AudioManager.MODE_NORMAL);
    }

    private void requestFocus(int gain, int usage) {
        abandonFocus();
        if (Build.VERSION.SDK_INT >= 26) {
            AudioFocusRequest req = new AudioFocusRequest.Builder(gain)
                .setAudioAttributes(new AudioAttributes.Builder().setUsage(usage)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .setOnAudioFocusChangeListener(focusListener)
                .build();
            am.requestAudioFocus(req);
            focusRequest = req;
        } else {
            am.requestAudioFocus(focusListener, AudioManager.STREAM_MUSIC, gain);
            focusRequest = focusListener;
        }
    }

    private void abandonFocus() {
        if (focusRequest == null) return;
        if (Build.VERSION.SDK_INT >= 26 && focusRequest instanceof AudioFocusRequest) am.abandonAudioFocusRequest((AudioFocusRequest) focusRequest);
        else am.abandonAudioFocus(focusListener);
        focusRequest = null;
    }

    @Override
    protected void handleOnDestroy() {
        main.removeCallbacksAndMessages(null);
        resetRouting();
        abandonFocus();
        if (tts != null) tts.shutdown();
    }
}
