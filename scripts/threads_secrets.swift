import Foundation
import Security

// A separate helper cannot read, replace, or delete existing account credentials.
let mode = CommandLine.arguments.dropFirst().first ?? ""
func fail() -> Never { FileHandle.standardError.write(Data("native_operation_failed\n".utf8)); exit(1) }
do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let args = try JSONSerialization.jsonObject(with: data) as? [String: Any],
          args["account"] as? String == "threads_publish" else { fail() }
    var query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "jp.moco.sns-automation", kSecAttrAccount as String: "threads_publish"]
    if mode == "secret-add" {
        guard let value = args["value"] as? String else { fail() }
        query[kSecValueData as String] = Data(value.utf8)
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { fail() }
    } else if mode == "secret-get" || mode == "secret-has" {
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if mode == "secret-has" {
            print(status == errSecSuccess ? "true" : "false")
        } else {
            guard status == errSecSuccess, let value = result as? Data else { fail() }
            FileHandle.standardOutput.write(value)
        }
    } else { fail() }
} catch { fail() }
