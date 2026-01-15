import 'package:flutter/material.dart';

enum SavoNetworkImageShape {
  roundedRect,
  circle,
}

class SavoNetworkImage extends StatelessWidget {
  const SavoNetworkImage({
    super.key,
    required this.url,
    required this.width,
    required this.height,
    this.fit = BoxFit.cover,
    this.shape = SavoNetworkImageShape.roundedRect,
    this.borderRadius,
    this.backgroundColor,
    this.border,
    this.placeholderIcon = Icons.image_outlined,
    this.errorIcon = Icons.broken_image_outlined,
    this.iconColor,
    this.iconSize,
    this.placeholder,
    this.error,
  });

  final String? url;
  final double width;
  final double height;
  final BoxFit fit;
  final SavoNetworkImageShape shape;
  final BorderRadius? borderRadius;
  final Color? backgroundColor;
  final BoxBorder? border;
  final IconData placeholderIcon;
  final IconData errorIcon;
  final Color? iconColor;
  final double? iconSize;
  final Widget? placeholder;
  final Widget? error;

  Widget _sized(Widget child) {
    return SizedBox(
      width: width.isFinite ? width : null,
      height: height.isFinite ? height : null,
      child: child,
    );
  }

  Widget _box(BuildContext context, IconData icon) {
    final bg = backgroundColor ?? Colors.grey.shade200;
    final ic = iconColor ?? Colors.black38;
    final size = iconSize ?? (width < 80 ? 18 : 36);

    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: bg,
        border: border,
        borderRadius: shape == SavoNetworkImageShape.roundedRect
            ? (borderRadius ?? BorderRadius.circular(12))
            : null,
        shape: shape == SavoNetworkImageShape.circle ? BoxShape.circle : BoxShape.rectangle,
      ),
      alignment: Alignment.center,
      child: Icon(icon, color: ic, size: size),
    );
  }

  @override
  Widget build(BuildContext context) {
    final trimmed = (url ?? '').trim();
    if (trimmed.isEmpty) {
      return placeholder != null ? _sized(placeholder!) : _box(context, placeholderIcon);
    }

    final image = Image.network(
      trimmed,
      width: width,
      height: height,
      fit: fit,
      loadingBuilder: (context, child, loadingProgress) {
        if (loadingProgress == null) return child;
        return placeholder != null ? _sized(placeholder!) : _box(context, placeholderIcon);
      },
      errorBuilder: (context, error, stackTrace) {
        return this.error != null ? _sized(this.error!) : _box(context, errorIcon);
      },
    );

    if (shape == SavoNetworkImageShape.circle) {
      return ClipOval(child: image);
    }

    return ClipRRect(
      borderRadius: borderRadius ?? BorderRadius.circular(12),
      child: image,
    );
  }
}

class SavoNetworkImageThumb extends StatelessWidget {
  const SavoNetworkImageThumb.roundedRect({
    super.key,
    required this.url,
    this.size = 44,
    this.borderRadius = const BorderRadius.all(Radius.circular(10)),
    this.backgroundColor,
    this.border,
    this.placeholderIcon = Icons.photo_outlined,
    this.errorIcon = Icons.broken_image_outlined,
    this.iconColor,
  }) : shape = SavoNetworkImageShape.roundedRect;

  const SavoNetworkImageThumb.circle({
    super.key,
    required this.url,
    this.size = 40,
    this.backgroundColor,
    this.border,
    this.placeholderIcon = Icons.image_outlined,
    this.errorIcon = Icons.broken_image_outlined,
    this.iconColor,
  })  : shape = SavoNetworkImageShape.circle,
        borderRadius = null;

  final String? url;
  final double size;
  final SavoNetworkImageShape shape;
  final BorderRadius? borderRadius;
  final Color? backgroundColor;
  final BoxBorder? border;
  final IconData placeholderIcon;
  final IconData errorIcon;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    return SavoNetworkImage(
      url: url,
      width: size,
      height: size,
      shape: shape,
      borderRadius: borderRadius,
      backgroundColor: backgroundColor,
      border: border,
      placeholderIcon: placeholderIcon,
      errorIcon: errorIcon,
      iconColor: iconColor,
      iconSize: shape == SavoNetworkImageShape.circle ? 18 : 18,
    );
  }
}
