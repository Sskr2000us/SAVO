import 'package:flutter/material.dart';

class QuickConfirmationCard extends StatefulWidget {
  final Map<String, dynamic> ingredient;
  final ValueChanged<Map<String, dynamic>> onConfirm;
  final VoidCallback onReject;

  const QuickConfirmationCard({
    super.key,
    required this.ingredient,
    required this.onConfirm,
    required this.onReject,
  });

  @override
  State<QuickConfirmationCard> createState() => _QuickConfirmationCardState();
}

class _QuickConfirmationCardState extends State<QuickConfirmationCard> {
  late final TextEditingController _quantityController;
  late String _selectedUnit;
  late String _selectedName;

  bool _isConfirming = false;
  bool _showAlternatives = false;
  bool _showAdjust = false;

  @override
  void initState() {
    super.initState();

    final initialName = (widget.ingredient['detected_name'] ?? widget.ingredient['name'] ?? 'Unknown').toString();
    _selectedName = initialName;

    _quantityController = TextEditingController(
      text: (widget.ingredient['quantity'] ?? widget.ingredient['estimated_quantity'] ?? 1.0).toString(),
    );
    _selectedUnit = (widget.ingredient['unit'] ?? 'pieces').toString();
  }

  @override
  void dispose() {
    _quantityController.dispose();
    super.dispose();
  }

  double _confidence() {
    final raw = widget.ingredient['confidence'];
    if (raw is num) return raw.toDouble();
    return double.tryParse(raw?.toString() ?? '') ?? 0.0;
  }

  Color _confidenceColor(double c) {
    if (c >= 0.8) return Colors.green;
    if (c >= 0.5) return Colors.orange;
    return Colors.red;
  }

  String _confidenceLabel(double c) {
    final percent = (c * 100).clamp(0, 100).toInt();
    if (c >= 0.8) return '$percent% confident';
    if (c >= 0.5) return '$percent% somewhat sure';
    return '$percent% uncertain';
  }

  List<String> _alternatives() {
    final raw = widget.ingredient['close_alternatives'];
    if (raw is! List) return const [];

    final out = <String>[];
    for (final alt in raw) {
      if (alt is Map) {
        final name = (alt['name'] ?? alt['detected_name'] ?? '').toString().trim();
        if (name.isNotEmpty) out.add(name);
      } else {
        final name = alt.toString().trim();
        if (name.isNotEmpty) out.add(name);
      }
    }
    return out;
  }

  Future<void> _confirm() async {
    if (_isConfirming) return;

    final name = _selectedName.toString().trim();
    if (name.isEmpty || name.toLowerCase() == 'unknown') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not identify item. Please retake.')),
      );
      return;
    }

    setState(() => _isConfirming = true);

    final qty = double.tryParse(_quantityController.text) ?? 1.0;
    final unit = _selectedUnit.trim().isEmpty ? 'pieces' : _selectedUnit.trim();

    final confirmed = Map<String, dynamic>.from(widget.ingredient);
    confirmed['name'] = name;
    confirmed['detected_name'] = name;
    confirmed['quantity'] = qty <= 0 ? 1.0 : qty;
    confirmed['unit'] = unit;
    confirmed['confidence'] = _confidence();

    widget.onConfirm(confirmed);
  }

  @override
  Widget build(BuildContext context) {
    final c = _confidence();
    final alternatives = _alternatives();

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.only(topLeft: Radius.circular(20), topRight: Radius.circular(20)),
      ),
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Is this correct?', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                const SizedBox(height: 14),
                Text(_selectedName, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _confidenceColor(c).withOpacity(0.2),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: _confidenceColor(c), width: 1),
                  ),
                  child: Text(
                    _confidenceLabel(c),
                    style: TextStyle(color: _confidenceColor(c), fontWeight: FontWeight.w600),
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        onPressed: _isConfirming ? null : _confirm,
                        child: _isConfirming
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Text('Yes'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _isConfirming
                            ? null
                            : () => setState(() {
                                  _showAlternatives = !_showAlternatives;
                                }),
                        child: const Text('Pick other'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: TextButton(
                        onPressed: _isConfirming ? null : widget.onReject,
                        child: const Text('Retake'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () => setState(() => _showAdjust = !_showAdjust),
                    child: Text(_showAdjust ? 'Hide quantity' : 'Adjust quantity'),
                  ),
                ),
                if (_showAdjust) ...[
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: TextField(
                          controller: _quantityController,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          decoration: InputDecoration(
                            labelText: 'Quantity',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 1,
                        child: DropdownButtonFormField<String>(
                          value: _selectedUnit,
                          decoration: InputDecoration(
                            labelText: 'Unit',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                          items: const [
                            DropdownMenuItem(value: 'pieces', child: Text('pieces')),
                            DropdownMenuItem(value: 'grams', child: Text('g')),
                            DropdownMenuItem(value: 'kg', child: Text('kg')),
                            DropdownMenuItem(value: 'ml', child: Text('ml')),
                            DropdownMenuItem(value: 'liters', child: Text('L')),
                            DropdownMenuItem(value: 'oz', child: Text('oz')),
                            DropdownMenuItem(value: 'lbs', child: Text('lbs')),
                            DropdownMenuItem(value: 'cups', child: Text('cups')),
                          ],
                          onChanged: (value) {
                            if (value == null) return;
                            setState(() => _selectedUnit = value);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
                if (_showAlternatives && alternatives.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  const Text('Or did you mean:', style: TextStyle(fontSize: 14, color: Colors.grey)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: alternatives.take(6).map((altName) {
                      return ActionChip(
                        label: Text(altName),
                        onPressed: () {
                          setState(() {
                            _selectedName = altName;
                          });
                        },
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
