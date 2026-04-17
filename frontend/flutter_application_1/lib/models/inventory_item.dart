class InventoryItem {
  final int? id;
  final String name;
  final String genericName;
  int quantity;

  InventoryItem({
    this.id,
    required this.name,
    required this.genericName,
    required this.quantity,
  });

  Map<String, dynamic> toMap() => {
    if (id != null) 'id': id,
    'name': name,
    'generic_name': genericName,
    'quantity': quantity,
  };

  factory InventoryItem.fromMap(Map<String, dynamic> map) => InventoryItem(
    id: map['id'] as int?,
    name: map['name'] as String,
    genericName: map['generic_name'] as String,
    quantity: map['quantity'] as int,
  );
}
