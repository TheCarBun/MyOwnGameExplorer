from PIL import Image, ImageDraw


def create_app_icon(size, colors):
    image = Image.new("RGBA", (size, size), colors["surface"])
    draw = ImageDraw.Draw(image)
    inset = max(1, size // 32)
    draw.rounded_rectangle(
        (inset, inset, size - inset - 1, size - inset - 1),
        radius=size // 5,
        fill=colors["icon_tile"],
        outline=colors["border"],
        width=max(1, size // 24),
    )
    center = size // 2
    draw.polygon(
        [
            (center - size // 9, center - size // 5),
            (center + size // 5, center),
            (center - size // 9, center + size // 5),
        ],
        fill=colors["accent"],
    )
    return image
