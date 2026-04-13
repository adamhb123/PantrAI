import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

void main() {
  runApp(const BarcodeScannerApp());
}

class BarcodeScannerApp extends StatelessWidget {
  const BarcodeScannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: BarcodeScannerScreen(),
    );
  }
}

class BarcodeScannerScreen extends StatefulWidget {
  const BarcodeScannerScreen({super.key});

  @override
  State<BarcodeScannerScreen> createState() => _BarcodeScannerScreenState();
}

class _BarcodeScannerScreenState extends State<BarcodeScannerScreen> {
  String barcodeResult = "Point the camera at a barcode";

  final MobileScannerController _controller = MobileScannerController(
    formats: [
      BarcodeFormat.ean13,
      BarcodeFormat.ean8,
      BarcodeFormat.upcA,
      BarcodeFormat.upcE,
      BarcodeFormat.code128,
      BarcodeFormat.code39,
      BarcodeFormat.code93,
      BarcodeFormat.itf14,
      BarcodeFormat.codabar,
    ],
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Barcode Scanner")),
      body: Column(
        children: [
          Expanded(
            flex: 3,
            child: MobileScanner(
              controller: _controller,
              onDetect: (BarcodeCapture capture) {
               final List<Barcode> barcodes = capture.barcodes;
                if (barcodes.isNotEmpty && barcodes.first.rawValue != null) {
                  setState(() {
                    barcodeResult = barcodes.first.rawValue!;
                  });
                }
              },
            ),
          ),
          Expanded(
            flex: 1,
            child: Center(
              child: Text(
                barcodeResult,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }
}