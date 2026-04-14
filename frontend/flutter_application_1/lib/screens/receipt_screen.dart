import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../api/pantrai_api.dart';
import '../db/database_helper.dart';

enum _ReceiptState { idle, loading, confirm, error }

class ReceiptScreen extends StatefulWidget {
  const ReceiptScreen({super.key});

  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  _ReceiptState _state = _ReceiptState.idle;
  ReceiptResult? _result;
  List<bool> _selected = [];
  String? _errorMessage;

  Future<void> _captureAndProcess() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 85,
      preferredCameraDevice: CameraDevice.rear,
    );
    if (picked == null) return;

    setState(() => _state = _ReceiptState.loading);

    try {
      final result = await PantrAIApi.extractReceipts(File(picked.path));
      if (result.items.isEmpty) {
        throw Exception('No items found on receipt. Try a clearer photo.');
      }
      setState(() {
        _result = result;
        _selected = List.filled(result.items.length, true);
        _state = _ReceiptState.confirm;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _state = _ReceiptState.error;
      });
    }
  }

  Future<void> _addToInventory() async {
    final items = _result!.items;
    for (var i = 0; i < items.length; i++) {
      if (_selected[i]) {
        await DatabaseHelper.instance.upsertItem(
          items[i].name,
          items[i].genericName,
          items[i].quantity,
        );
      }
    }
    if (mounted) {
      final count = _selected.where((s) => s).length;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Added $count item(s) to inventory')),
      );
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan Receipt')),
      body: switch (_state) {
        _ReceiptState.idle => _buildIdle(),
        _ReceiptState.loading => _buildLoading(),
        _ReceiptState.confirm => _buildConfirm(),
        _ReceiptState.error => _buildError(),
      },
    );
  }

  Widget _buildIdle() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.receipt_long, size: 80, color: Colors.grey),
            const SizedBox(height: 24),
            const Text(
              'Take a photo of your receipt.\nHold the phone in portrait orientation and align the full receipt within the frame.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: _captureAndProcess,
              icon: const Icon(Icons.camera_alt),
              label: const Text('Take Photo'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoading() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text(
            'Processing receipt…\nThis may take a moment.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildConfirm() {
    final items = _result!.items;
    final headerParts = [
      if (_result!.store != null) _result!.store!,
      if (_result!.date != null) _result!.date!,
    ];

    return Column(
      children: [
        if (headerParts.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text(
              headerParts.join(' · '),
              style: const TextStyle(color: Colors.grey),
            ),
          ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: items.length,
            itemBuilder: (context, i) {
              final item = items[i];
              final qtyController = TextEditingController(
                text: item.quantity.toString(),
              );
              return CheckboxListTile(
                value: _selected[i],
                onChanged: (v) => setState(() => _selected[i] = v ?? false),
                title: Text(item.name),
                subtitle: item.genericName.isNotEmpty
                    ? Text(item.genericName, style: const TextStyle(color: Colors.grey))
                    : null,
                secondary: SizedBox(
                  width: 64,
                  child: TextField(
                    controller: qtyController,
                    keyboardType: TextInputType.number,
                    textAlign: TextAlign.center,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(vertical: 8),
                    ),
                    onChanged: (v) {
                      final qty = int.tryParse(v);
                      if (qty != null && qty > 0) item.quantity = qty;
                    },
                  ),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ElevatedButton(
                onPressed: _selected.any((s) => s) ? _addToInventory : null,
                child: Text(
                  'Add ${_selected.where((s) => s).length} Item(s) to Inventory',
                ),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => setState(() => _state = _ReceiptState.idle),
                child: const Text('Retake Photo'),
              ),
            ],
          ),
        ),
      ],
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
            'Extraction failed',
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
          ElevatedButton(
            onPressed: () => setState(() => _state = _ReceiptState.idle),
            child: const Text('Try Again'),
          ),
        ],
      ),
    );
  }
}
