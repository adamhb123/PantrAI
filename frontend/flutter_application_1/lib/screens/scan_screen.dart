import 'package:flutter/material.dart';
import 'barcode_screen.dart';
import 'item_screen.dart';
import 'receipt_screen.dart';

class ScanScreen extends StatelessWidget {
  const ScanScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan')),
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _ScanButton(
              icon: Icons.qr_code_scanner,
              label: 'Barcode',
              description: 'Scan a product UPC barcode',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const BarcodeScreen()),
              ),
            ),
            const SizedBox(height: 20),
            _ScanButton(
              icon: Icons.image_search,
              label: 'Item',
              description: 'Photograph a grocery item',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ItemScreen()),
              ),
            ),
            const SizedBox(height: 20),
            _ScanButton(
              icon: Icons.receipt_long,
              label: 'Receipt',
              description: 'Photograph a store receipt',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ReceiptScreen()),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScanButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String description;
  final VoidCallback onTap;

  const _ScanButton({
    required this.icon,
    required this.label,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onTap,
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 24),
        alignment: Alignment.centerLeft,
      ),
      child: Row(
        children: [
          Icon(icon, size: 32),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              Text(description, style: const TextStyle(fontSize: 13)),
            ],
          ),
        ],
      ),
    );
  }
}
