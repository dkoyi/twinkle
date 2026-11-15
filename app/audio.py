"""G.711 μ-law and mono PCM conversion without the removed audioop module."""
import base64
import numpy as np


def mulaw_to_pcm16(data: bytes) -> np.ndarray:
    """Decode G.711 bytes to signed 16-bit samples at the original rate."""
    codes = np.bitwise_not(np.frombuffer(data, dtype=np.uint8)).astype(np.int32)
    value = (((codes & 15) << 3) + 132) << ((codes >> 4) & 7)
    return np.where(codes & 128, 132 - value, value - 132).astype(np.int16)


def pcm16_to_mulaw(samples: np.ndarray) -> bytes:
    """Encode signed PCM samples as standard G.711 μ-law bytes."""
    values = np.asarray(samples, dtype=np.int16).astype(np.int32)
    sign = np.where(values < 0, 128, 0)
    magnitude = np.minimum(np.abs(values), 32635) + 132
    exponent = np.maximum(np.floor(np.log2(magnitude)).astype(np.int32) - 7, 0)
    mantissa = (magnitude >> (exponent + 3)) & 15
    return ((~(sign | (exponent << 4) | mantissa)) & 255).astype(np.uint8).tobytes()


def resample(samples: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    """Resample mono PCM using linear interpolation, retaining duration."""
    if src_hz <= 0 or dst_hz <= 0:
        raise ValueError("Sample rates must be positive")
    samples = np.asarray(samples, dtype=np.int16)
    if not len(samples) or src_hz == dst_hz:
        return samples.copy()
    count = round(len(samples) * dst_hz / src_hz)
    return np.rint(np.interp(np.arange(count) * src_hz / dst_hz,
                            np.arange(len(samples)), samples)).astype(np.int16)


def twilio_in_to_gemini(payload_b64: str) -> bytes:
    """Decode 8 kHz μ-law base64 to little-endian PCM16 at 16 kHz."""
    samples = mulaw_to_pcm16(base64.b64decode(payload_b64, validate=True))
    return resample(samples, 8000, 16000).astype('<i2').tobytes()


def gemini_out_to_twilio(pcm24k: bytes) -> list[str]:
    """Convert PCM24k to 20 ms μ-law frames; pad the last with silence.

    For streaming, buffer PCM into 960-byte blocks before calling this.
    """
    samples = np.frombuffer(pcm24k, dtype='<i2')
    raw = pcm16_to_mulaw(resample(samples, 24000, 8000))
    return [base64.b64encode(raw[i:i + 160].ljust(160, b'\xff')).decode()
            for i in range(0, len(raw), 160)]
