import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../constants.dart';
import '../api/pantrai_api.dart';
import '../db/database_helper.dart';

enum _BarcodeState { scanning, loading, confirm, error }

class BarcodeScreen extends StatefulWidget {
  const BarcodeScreen({super.key});

  @override
  State<BarcodeScreen> createState() => _BarcodeScreenState();
}

class _BarcodeScreenState extends State<BarcodeScreen> {
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

  _BarcodeState _state = _BarcodeState.scanning;
  String? _lastDetected;
  int _consecutiveCount = 0;
  String? _confirmedBarcode;
  String? _itemName;
  String? _errorMessage;
  int _quantity = 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_state != _BarcodeState.scanning) return;
    final value = capture.barcodes.firstOrNull?.rawValue;

    if (value == null || value != _lastDetected) {
      _lastDetected = value;
      _consecutiveCount = value == null ? 0 : 1;
      return;
    }

    _consecutiveCount++;
    if (_consecutiveCount >= kBarcodeScanThreshold) {
      _onBarcodeConfirmed(value);
    }
  }

  Future<void> _onBarcodeConfirmed(String barcode) async {
    setState(() {
      _state = _BarcodeState.loading;
      _confirmedBarcode = barcode;
    });
    await _controller.stop();

    try {
      final results = await PantrAIApi.getBarcodeItems([barcode]);
      final itemName = results.firstOrNull?.itemName;
      if (itemName == null || itemName.isEmpty) {
        throw Exception('Barcode not found in database');
      }
      setState(() {
        _itemName = itemName;
        _quantity = 1;
        _state = _BarcodeState.confirm;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _state = _BarcodeState.error;
      });
    }
  }

  Future<void> _addToInventory() async {
    if (_itemName == null) return;
    await DatabaseHelper.instance.upsertItem(_itemName!, '', _quantity);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Added "$_itemName" (×$_quantity) to inventory'),
        ),
      );
      Navigator.pop(context);
    }
  }

  void _retry() {
    setState(() {
      _lastDetected = null;
      _consecutiveCount = 0;
      _state = _BarcodeState.scanning;
      _errorMessage = null;
    });
    _controller.start();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan Barcode')),
      body: switch (_state) {
        _BarcodeState.scanning => _buildScanner(),
        _BarcodeState.loading => const Center(
          child: CircularProgressIndicator(),
        ),
        _BarcodeState.confirm => _buildConfirm(),
        _BarcodeState.error => _buildError(),
      },
    );
  }

  Widget _buildScanner() {
    return Stack(
      children: [
        MobileScanner(controller: _controller, onDetect: _onDetect),
        // Rectangular guide overlay
        Center(
          child: CustomPaint(
            size: const Size(280, 130),
            painter: _BarcodeGuide(),
          ),
        ),
        Positioned(
          bottom: 40,
          left: 0,
          right: 0,
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Align barcode within the guide',
                style: TextStyle(color: Colors.white),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildConfirm() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
          const SizedBox(height: 16),
          Text(
            _itemName ?? '',
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          Text(
            'Barcode: $_confirmedBarcode',
            style: const TextStyle(color: Colors.grey),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('Quantity:', style: TextStyle(fontSize: 18)),
              const SizedBox(width: 16),
              IconButton(
                icon: const Icon(Icons.remove_circle_outline),
                onPressed: () =>
                    setState(() => _quantity = (_quantity - 1).clamp(1, 999)),
              ),
              SizedBox(
                width: 48,
                child: Text(
                  '$_quantity',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.add_circle_outline),
                onPressed: () => setState(() => _quantity++),
              ),
            ],
          ),
          const SizedBox(height: 32),
          ElevatedButton(
            onPressed: _addToInventory,
            child: const Text('Add to Inventory'),
          ),
          const SizedBox(height: 12),
          TextButton(onPressed: _retry, child: const Text('Scan Again')),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          Text(
            'Could not look up barcode',
            style: Theme.of(context).textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            _errorMessage ?? 'Unknown error',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 32),
          ElevatedButton(onPressed: _retry, child: const Text('Try Again')),
        ],
      ),
    );
  }
}

class _BarcodeGuide extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(0, 0, size.width, size.height),
        const Radius.circular(12),
      ),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
