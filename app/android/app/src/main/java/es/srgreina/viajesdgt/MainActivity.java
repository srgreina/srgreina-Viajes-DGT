package es.srgreina.viajesdgt;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(VozCochePlugin.class); // voz por manos libres del coche (antes de super.onCreate)
        super.onCreate(savedInstanceState);
    }
}
