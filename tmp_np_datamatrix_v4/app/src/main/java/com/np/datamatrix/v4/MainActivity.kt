package com.np.datamatrix.v4

import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning

class MainActivity : ComponentActivity() {

    private lateinit var scanner: GmsBarcodeScanner
    private lateinit var status: TextView
    private lateinit var result: TextView
    private lateinit var scanButton: Button
    private var scanning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val options = GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_DATA_MATRIX)
            .enableAutoZoom()
            .build()

        scanner = GmsBarcodeScanning.getClient(this, options)
        buildUi()

        scanButton.postDelayed({ startScan() }, 450)
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24), dp(42), dp(24), dp(28))
            setBackgroundColor(Color.rgb(7, 25, 42))
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        val title = TextView(this).apply {
            text = "NP • DATAMATRIX V4"
            setTextColor(Color.WHITE)
            textSize = 30f
            gravity = Gravity.CENTER
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

        val subtitle = TextView(this).apply {
            text = "Scanner di sistema Google • DataMatrix"
            setTextColor(Color.rgb(164, 208, 242))
            textSize = 17f
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, dp(38))
        }

        status = TextView(this).apply {
            text = "Apertura scanner…"
            setTextColor(Color.rgb(193, 224, 248))
            textSize = 22f
            gravity = Gravity.CENTER
            setPadding(dp(12), dp(22), dp(12), dp(22))
        }

        val label = TextView(this).apply {
            text = "CODICE LETTO"
            setTextColor(Color.rgb(118, 194, 255))
            textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            gravity = Gravity.CENTER
        }

        result = TextView(this).apply {
            text = "—"
            setTextColor(Color.WHITE)
            textSize = 34f
            gravity = Gravity.CENTER
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(dp(10), dp(18), dp(10), dp(38))
            setTextIsSelectable(true)
        }

        scanButton = Button(this).apply {
            text = "SCANSIONA DATAMATRIX"
            textSize = 18f
            isAllCaps = false
            setOnClickListener { startScan() }
        }

        val note = TextView(this).apply {
            text = "Questa versione non usa più la fotocamera interna dell'app: usa lo scanner ottimizzato di Google Play Services con auto-zoom. Inquadra lo stesso codice che la fotocamera Samsung legge come SUG007."
            setTextColor(Color.rgb(191, 205, 217))
            textSize = 15f
            gravity = Gravity.CENTER
            setPadding(dp(4), dp(30), dp(4), 0)
        }

        root.addView(title, lpMatchWrap())
        root.addView(subtitle, lpMatchWrap())
        root.addView(status, lpMatchWrap())
        root.addView(label, lpMatchWrap())
        root.addView(result, lpMatchWrap())
        root.addView(scanButton, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(62)
        ))
        root.addView(note, lpMatchWrap())

        setContentView(root)
    }

    private fun startScan() {
        if (scanning) return
        scanning = true
        scanButton.isEnabled = false
        status.text = "Inquadra il DataMatrix…"
        status.setTextColor(Color.rgb(193, 224, 248))

        scanner.startScan()
            .addOnSuccessListener { barcode ->
                val value = barcode.rawValue?.trim().orEmpty().ifBlank {
                    barcode.displayValue?.trim().orEmpty()
                }

                if (value.isNotBlank()) {
                    result.text = value
                    status.text = "✓ DATAMATRIX LETTO"
                    status.setTextColor(Color.rgb(74, 255, 140))
                } else {
                    result.text = "—"
                    status.text = "Codice rilevato ma senza valore"
                    status.setTextColor(Color.rgb(255, 190, 90))
                }
            }
            .addOnCanceledListener {
                status.text = "Scansione annullata"
                status.setTextColor(Color.rgb(193, 224, 248))
            }
            .addOnFailureListener { e ->
                status.text = "Errore scanner: ${e.message ?: "riprova"}"
                status.setTextColor(Color.rgb(255, 120, 120))
            }
            .addOnCompleteListener {
                scanning = false
                scanButton.isEnabled = true
                scanButton.text = "SCANSIONA DI NUOVO"
            }
    }

    private fun lpMatchWrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    )

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
