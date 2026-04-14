import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../api/pantrai_api.dart';
import '../db/database_helper.dart';

enum _ItemState { idle, loading, confirm, error }

class ItemScreen extends StatefulWidget {
  const ItemScreen({super.key});

  @override
  State<ItemScreen> createState() => _ItemScreenState();
}

class _ItemScreenState extends State<ItemScreen> {
  _ItemState _state = _ItemState.idle;
  List<ExtractedItem> _items = [];
  List<bool> _selected = [];
  String? _errorMessage;

  Future<void> _captureAndProcess() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 85,
    );
    if (picked == null) return;

    setState(() => _state = _ItemState.loading);

    try {
      final results = await PantrAIApi.extractItems(File(picked.path));
      if (results.isEmpty) {
        throw Exception('No items detected. Try a clearer photo.');
      }
      setState(() {
        _items = results;
        _selected = List.filled(results.length, true);
        _state = _ItemState.confirm;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _state = _ItemState.error;
      });
    }
  }

  Future<void> _addToInventory() async {
    for (var i = 0; i < _items.length; i++) {
      if (_selected[i]) {
        await DatabaseHelper.instance.upsertItem(
          _items[i].name,
          _items[i].genericName,
          _items[i].quantity,
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
      appBar: AppBar(title: const Text('Scan Item')),
      body: switch (_state) {
        _ItemState.idle => _buildIdle(),
        _ItemState.loading => _buildLoading(),
        _ItemState.confirm => _buildConfirm(),
        _ItemState.error => _buildError(),
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
            const Icon(Icons.camera_alt, size: 80, color: Colors.grey),
            const SizedBox(height: 24),
            const Text(
              'Take a photo of a grocery item to identify it.',
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
          Text('Identifying item...'),
        ],
      ),
    );
  }

  Widget _buildConfirm() {
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: _items.length,
            itemBuilder: (context, i) {
              final item = _items[i];
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
                onPressed: () => setState(() => _state = _ItemState.idle),
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
            onPressed: () => setState(() => _state = _ItemState.idle),
            child: const Text('Try Again'),
          ),
        ],
      ),
    );
  }
}
