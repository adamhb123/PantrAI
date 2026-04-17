import 'package:flutter/material.dart';
import '../db/database_helper.dart';
import '../models/inventory_item.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<InventoryItem>> _itemsFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() {
      _itemsFuture = DatabaseHelper.instance.getAllItems();
    });
  }

  Future<void> _confirmDelete(InventoryItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Item Entry?'),
        content: Text('Remove "${item.name}" from inventory?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed == true && item.id != null) {
      await DatabaseHelper.instance.deleteItem(item.id!);
      _reload();
    }
  }

  Future<void> _onQuantitySubmitted(InventoryItem item, String value) async {
    final qty = int.tryParse(value);
    if (qty == null) return;
    if (qty <= 0) {
      await _confirmDelete(item);
    } else if (item.id != null) {
      await DatabaseHelper.instance.updateQuantity(item.id!, qty);
      _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Inventory')),
      body: FutureBuilder<List<InventoryItem>>(
        future: _itemsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final items = snapshot.data ?? [];
          if (items.isEmpty) {
            return const Center(
              child: Text(
                'No items yet.\nGo to Scan to add something!',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, color: Colors.grey),
              ),
            );
          }
          return ListView.builder(
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              return _InventoryRow(
                item: item,
                onDelete: () => _confirmDelete(item),
                onQuantitySubmitted: (v) => _onQuantitySubmitted(item, v),
              );
            },
          );
        },
      ),
    );
  }
}

class _InventoryRow extends StatefulWidget {
  final InventoryItem item;
  final VoidCallback onDelete;
  final ValueChanged<String> onQuantitySubmitted;

  const _InventoryRow({
    required this.item,
    required this.onDelete,
    required this.onQuantitySubmitted,
  });

  @override
  State<_InventoryRow> createState() => _InventoryRowState();
}

class _InventoryRowState extends State<_InventoryRow> {
  late final TextEditingController _qtyController;

  @override
  void initState() {
    super.initState();
    _qtyController = TextEditingController(
      text: widget.item.quantity.toString(),
    );
  }

  @override
  void didUpdateWidget(_InventoryRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.quantity != widget.item.quantity) {
      _qtyController.text = widget.item.quantity.toString();
    }
  }

  @override
  void dispose() {
    _qtyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey(widget.item.id),
      direction: DismissDirection.startToEnd,
      confirmDismiss: (_) async {
        widget.onDelete();
        return false; // dismiss handled manually after dialog
      },
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      child: ListTile(
        title: Text(widget.item.name, overflow: TextOverflow.ellipsis),
        subtitle: widget.item.genericName.isNotEmpty
            ? Text(
                widget.item.genericName,
                style: const TextStyle(color: Colors.grey, fontSize: 12),
              )
            : null,
        trailing: SizedBox(
          width: 72,
          child: TextField(
            controller: _qtyController,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            onSubmitted: widget.onQuantitySubmitted,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(vertical: 8),
            ),
          ),
        ),
      ),
    );
  }
}
