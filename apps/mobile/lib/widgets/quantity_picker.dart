import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Reusable widget for picking quantity and unit
class QuantityPicker extends StatefulWidget {
  final double initialQuantity;
  final String initialUnit;
  final List<String> availableUnits;
  final Function(double quantity, String unit) onChanged;
  final bool enabled;

  const QuantityPicker({
    Key? key,
    required this.initialQuantity,
    required this.initialUnit,
    required this.availableUnits,
    required this.onChanged,
    this.enabled = true,
  }) : super(key: key);

  @override
  State<QuantityPicker> createState() => _QuantityPickerState();
}

class _QuantityPickerState extends State<QuantityPicker> {
  late double _quantity;
  late String _unit;
  late TextEditingController _textController;

  @override
  void initState() {
    super.initState();
    _quantity = widget.initialQuantity;
    _unit = widget.initialUnit;
    _textController = TextEditingController(text: _formatQuantity(_quantity));
  }

  @override
  void didUpdateWidget(QuantityPicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialQuantity != widget.initialQuantity ||
        oldWidget.initialUnit != widget.initialUnit) {
      _quantity = widget.initialQuantity;
      _unit = widget.initialUnit;
      _textController.text = _formatQuantity(_quantity);
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  String _formatQuantity(double qty) {
    // Remove trailing zeros and decimal point if not needed
    if (qty == qty.roundToDouble()) {
      return qty.toInt().toString();
    } else {
      return qty.toStringAsFixed(2).replaceAll(RegExp(r'0*$'), '').replaceAll(RegExp(r'\.$'), '');
    }
  }

  void _increment() {
    if (!widget.enabled) return;
    
    setState(() {
      // Smart increment based on current value
      if (_quantity < 1) {
        _quantity += 0.25; // Smaller increments for small values
      } else if (_quantity < 10) {
        _quantity += 0.5;
      } else if (_quantity < 100) {
        _quantity += 1;
      } else {
        _quantity += 10;
      }
      _textController.text = _formatQuantity(_quantity);
      widget.onChanged(_quantity, _unit);
    });
  }

  void _decrement() {
    if (!widget.enabled) return;
    
    setState(() {
      // Smart decrement based on current value
      double decrement;
      if (_quantity <= 1) {
        decrement = 0.25;
      } else if (_quantity <= 10) {
        decrement = 0.5;
      } else if (_quantity <= 100) {
        decrement = 1;
      } else {
        decrement = 10;
      }
      
      _quantity = (_quantity - decrement).clamp(0.25, double.infinity);
      _textController.text = _formatQuantity(_quantity);
      widget.onChanged(_quantity, _unit);
    });
  }

  void _handleTextChange(String value) {
    if (!widget.enabled) return;
    
    final qty = double.tryParse(value);
    if (qty != null && qty > 0) {
      setState(() {
        _quantity = qty;
        widget.onChanged(_quantity, _unit);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final borderColor = theme.dividerColor;
    final enabledBackground = colorScheme.surface;
    final disabledBackground = colorScheme.surface.withOpacity(0.6);
    final enabledTextColor = colorScheme.onSurface;
    final disabledTextColor = theme.disabledColor;

    final quantityTextStyle = theme.textTheme.bodyLarge?.copyWith(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: widget.enabled ? enabledTextColor : disabledTextColor,
        ) ??
        TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: widget.enabled ? enabledTextColor : disabledTextColor,
        );

    final unitTextStyle = theme.textTheme.bodyMedium?.copyWith(
          fontSize: 14,
          color: widget.enabled ? enabledTextColor : disabledTextColor,
        ) ??
        TextStyle(
          fontSize: 14,
          color: widget.enabled ? enabledTextColor : disabledTextColor,
        );

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Decrement button
          IconButton(
            icon: const Icon(Icons.remove_circle_outline),
            color: widget.enabled ? const Color(0xFF4CAF50) : Colors.grey,
            onPressed: widget.enabled ? _decrement : null,
            tooltip: 'Decrease quantity',
          ),
          
          // Quantity input field
          Container(
            width: 70,
            height: 40,
            decoration: BoxDecoration(
              border: Border.all(color: borderColor),
              borderRadius: BorderRadius.circular(8),
              color: widget.enabled ? enabledBackground : disabledBackground,
            ),
            child: TextField(
              controller: _textController,
              enabled: widget.enabled,
              textAlign: TextAlign.center,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}')),
              ],
              style: quantityTextStyle,
              decoration: const InputDecoration(
                border: InputBorder.none,
                contentPadding: EdgeInsets.symmetric(horizontal: 4, vertical: 8),
              ),
              onChanged: _handleTextChange,
            ),
          ),
          
          // Increment button
          IconButton(
            icon: const Icon(Icons.add_circle_outline),
            color: widget.enabled ? const Color(0xFF4CAF50) : Colors.grey,
            onPressed: widget.enabled ? _increment : null,
            tooltip: 'Increase quantity',
          ),
          
          const SizedBox(width: 8),
          
          // Unit dropdown
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              border: Border.all(color: borderColor),
              borderRadius: BorderRadius.circular(8),
              color: widget.enabled ? enabledBackground : disabledBackground,
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: widget.availableUnits.contains(_unit) ? _unit : widget.availableUnits.first,
                items: widget.availableUnits.map((unit) {
                  return DropdownMenuItem(
                    value: unit,
                    child: Text(
                      unit,
                      style: unitTextStyle,
                    ),
                  );
                }).toList(),
                onChanged: widget.enabled ? (newUnit) {
                  if (newUnit != null) {
                    setState(() {
                      _unit = newUnit;
                      widget.onChanged(_quantity, _unit);
                    });
                  }
                } : null,
                icon: const Icon(Icons.arrow_drop_down, size: 20),
                iconEnabledColor: enabledTextColor,
                iconDisabledColor: disabledTextColor,
                style: unitTextStyle,
                dropdownColor: enabledBackground,
                isDense: true,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Helper function to get smart unit suggestions based on ingredient category
List<String> getSmartUnitSuggestions(String? category, String? ingredientName) {
  final name = ingredientName?.toLowerCase() ?? '';
  
  // Specific ingredient overrides
  if (name.contains('milk') || name.contains('juice') || name.contains('water') ||
      name.contains('broth') || name.contains('stock')) {
    return ['ml', 'liters', 'cups', 'fl oz'];
  }
  
  if (name.contains('rice') || name.contains('flour') || name.contains('sugar') ||
      name.contains('salt')) {
    return ['grams', 'kg', 'cups', 'tbsp', 'tsp'];
  }
  
  if (name.contains('oil') || name.contains('vinegar') || name.contains('sauce')) {
    return ['ml', 'tbsp', 'tsp', 'cups'];
  }
  
  if (name.contains('egg') || name.contains('onion') || name.contains('tomato') ||
      name.contains('potato') || name.contains('apple')) {
    return ['pieces', 'items', 'grams'];
  }
  
  // Category-based defaults
  switch (category?.toLowerCase()) {
    case 'vegetable':
    case 'fruit':
      return ['pieces', 'grams', 'kg', 'items'];
    
    case 'dairy':
    case 'beverage':
      return ['ml', 'liters', 'cups', 'fl oz'];
    
    case 'protein':
    case 'meat':
    case 'seafood':
      return ['grams', 'kg', 'lb', 'oz', 'pieces'];
    
    case 'grain':
    case 'pasta':
      return ['grams', 'kg', 'cups', 'oz'];
    
    case 'spice':
    case 'herb':
      return ['tsp', 'tbsp', 'grams', 'pinch'];
    
    case 'condiment':
      return ['ml', 'tbsp', 'tsp', 'cups'];
    
    default:
      return ['pieces', 'grams', 'ml', 'cups', 'items'];
  }
}
