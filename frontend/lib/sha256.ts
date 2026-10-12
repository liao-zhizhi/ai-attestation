import { sha256 } from "js-sha256";

/** 把 ArrayBuffer / TypedArray 收成字节，供纯 JS SHA-256 使用。 */
function toBytes(data: BufferSource): Uint8Array {
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
}

/** 浏览器本地 SHA-256（UTF-8 文本或文件字节），不把原文发给服务器。

不使用 crypto.subtle：线上 HTTP 不是安全上下文，subtle 为 undefined。
输出为 64 位小写 hex，与 Python hashlib.sha256 一致。
*/
export async function sha256Hex(data: BufferSource): Promise<string> {
  return sha256(toBytes(data));
}
