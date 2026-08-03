import AppKit

guard CommandLine.arguments.count == 2 else { fatalError("iconset output required") }
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

let variants: [(String, Int)] = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]

for (name, pixels) in variants {
    let image = NSImage(size: NSSize(width: pixels, height: pixels))
    image.lockFocus()
    NSGraphicsContext.current?.imageInterpolation = .high
    let frame = NSRect(x: 0, y: 0, width: pixels, height: pixels)
    let inset = CGFloat(pixels) * 0.045
    let tile = frame.insetBy(dx: inset, dy: inset)
    let radius = CGFloat(pixels) * 0.22
    let background = NSBezierPath(roundedRect: tile, xRadius: radius, yRadius: radius)
    NSColor(calibratedRed: 0.07, green: 0.075, blue: 0.07, alpha: 1).setFill()
    background.fill()

    let c = CGFloat(pixels) / 2
    let r = CGFloat(pixels) * 0.205
    let diamond = NSBezierPath()
    diamond.move(to: NSPoint(x: c, y: c + r))
    diamond.line(to: NSPoint(x: c + r, y: c))
    diamond.line(to: NSPoint(x: c, y: c - r))
    diamond.line(to: NSPoint(x: c - r, y: c))
    diamond.close()
    NSColor(calibratedWhite: 0.97, alpha: 1).setFill()
    diamond.fill()

    let inner = NSBezierPath(ovalIn: NSRect(x: c - r * 0.19, y: c - r * 0.19,
                                             width: r * 0.38, height: r * 0.38))
    NSColor(calibratedRed: 0.11, green: 0.36, blue: 0.95, alpha: 1).setFill()
    inner.fill()
    image.unlockFocus()

    guard let tiff = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("could not render \(name)")
    }
    try png.write(to: output.appendingPathComponent(name))
}
