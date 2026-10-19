import AppKit
import Security

// Secrets enter through stdin and are never command-line arguments.
let mode = CommandLine.arguments.dropFirst().first ?? ""
func fail() -> Never { FileHandle.standardError.write(Data("native_operation_failed\n".utf8)); exit(1) }
do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let args = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { fail() }
    if mode.hasPrefix("secret-") {
        guard let account = args["account"] as? String,
              ["youtube", "instagram", "threads"].contains(account) else { fail() }
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
          kSecAttrService as String: "jp.moco.sns-automation", kSecAttrAccount as String: account]
        if mode == "secret-set" {
            guard let value = args["value"] as? String else { fail() }
            let update = [kSecValueData as String: Data(value.utf8)]
            let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
            if status == errSecItemNotFound {
                var add = query
                add[kSecValueData as String] = Data(value.utf8)
                add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
                guard SecItemAdd(add as CFDictionary, nil) == errSecSuccess else { fail() }
            } else if status != errSecSuccess { fail() }
        } else {
            var q = query
            q[kSecReturnData as String] = true
            q[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: CFTypeRef?
            let status = SecItemCopyMatching(q as CFDictionary, &result)
            if mode == "secret-has" {
                print(status == errSecSuccess ? "true" : "false")
            } else if mode == "secret-get", status == errSecSuccess, let d = result as? Data {
                FileHandle.standardOutput.write(d)
            } else { fail() }
        }
    } else if mode == "card" {
        guard let output = args["output"] as? String, let title = args["text"] as? String else { fail() }
        let w = 1080, h = 1920
        guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h,
          bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
          colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
          let context = NSGraphicsContext(bitmapImageRep: bitmap) else { fail() }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        NSColor(calibratedRed: 0.045, green: 0.065, blue: 0.12, alpha: 1).setFill()
        NSRect(x: 0, y: 0, width: w, height: h).fill()
        NSColor(calibratedRed: 0.46, green: 0.9, blue: 0.73, alpha: 1).setFill()
        NSRect(x: 76, y: 1500, width: 112, height: 12).fill()
        let p = NSMutableParagraphStyle()
        p.lineSpacing = 24
        p.lineBreakMode = .byCharWrapping
        var fontSize: CGFloat = title.count > 26 ? 72 : 92
        while fontSize > 38 {
            let bound = (title as NSString).boundingRect(with: NSSize(width: 928, height: 2000),
              options: [.usesLineFragmentOrigin, .usesFontLeading], attributes: [
                .font: NSFont.systemFont(ofSize: fontSize, weight: .bold), .paragraphStyle: p])
            if bound.height <= 790 { break }
            fontSize -= 2
        }
        (title as NSString).draw(in: NSRect(x: 76, y: 610, width: 928, height: 800), withAttributes: [
          .font: NSFont.systemFont(ofSize: fontSize, weight: .bold), .foregroundColor: NSColor.white,
          .paragraphStyle: p])
        ("MOCO  /  CREATOR NOTES" as NSString).draw(at: NSPoint(x: 76, y: 1580), withAttributes: [
          .font: NSFont.systemFont(ofSize: 30, weight: .medium),
          .foregroundColor: NSColor(calibratedRed: 0.46, green: 0.9, blue: 0.73, alpha: 1)])
        ("確認用ドラフト · 未公開" as NSString).draw(at: NSPoint(x: 76, y: 230), withAttributes: [
          .font: NSFont.systemFont(ofSize: 30), .foregroundColor: NSColor.lightGray])
        NSGraphicsContext.restoreGraphicsState()
        guard let png = bitmap.representation(using: .png, properties: [:]) else { fail() }
        try png.write(to: URL(fileURLWithPath: output), options: .atomic)
    } else { fail() }
} catch { fail() }
