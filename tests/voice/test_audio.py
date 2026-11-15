import base64
import numpy as np
from app.audio import mulaw_to_pcm16, pcm16_to_mulaw, resample, twilio_in_to_gemini, gemini_out_to_twilio


def test_known_g711_vectors():
    # ITU G.711 codewords: positive/negative silence and maximum magnitudes.
    assert mulaw_to_pcm16(bytes([0xff, 0x7f, 0x80, 0x00])).tolist() == [0, 0, 32124, -32124]
    assert pcm16_to_mulaw(np.array([0, 32124, -32124], dtype=np.int16)) == bytes([255, 128, 0])


def test_all_codewords_roundtrip_except_negative_zero():
    codes = bytes(range(256))
    result = pcm16_to_mulaw(mulaw_to_pcm16(codes))
    assert result[:127] == codes[:127]
    assert result[127] == 255
    assert result[128:] == codes[128:]


def test_audio_rates_and_frame_lengths():
    payload = base64.b64encode(b'\xff' * 160).decode()
    pcm = twilio_in_to_gemini(payload)
    assert len(pcm) == 640  # 20 ms at 16 kHz, 16 bits.
    assert not np.frombuffer(pcm, dtype='<i2').any()
    frames = gemini_out_to_twilio(b'\0' * 1920)
    assert len(frames) == 2
    assert all(base64.b64decode(frame) == b'\xff' * 160 for frame in frames)


def test_tone_pitch_and_duration_preserved():
    source = (np.sin(2 * np.pi * 440 * np.arange(24000) / 24000) * 10000).astype(np.int16)
    result = mulaw_to_pcm16(b''.join(base64.b64decode(x) for x in gemini_out_to_twilio(source.tobytes())))
    assert len(result) == 8000
    peak = np.argmax(abs(np.fft.rfft(result)))
    assert peak == 440
    assert resample(np.array([], dtype=np.int16), 8000, 16000).size == 0
