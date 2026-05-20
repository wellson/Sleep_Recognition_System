import math
import struct
import wave
import os

def create_directory():
    os.makedirs("assets", exist_ok=True)

def generate_pulsed_alarm(filename, freq=1000, duration_sec=1.5, volume=0.7, pulse_cycle=0.3, pulse_on=0.15, sample_rate=44100):
    """
    Generates a pulsed alarm wave file.
    Creates rapid beeps: e.g. Beep for 0.15s, silent for 0.15s, repeating.
    """
    path = os.path.join("assets", filename)
    num_samples = int(sample_rate * duration_sec)
    
    print(f"Gerando som de alarme: {path} (Freq: {freq}Hz, Duração: {duration_sec}s)")
    with wave.open(path, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            time = i / sample_rate
            # Check where we are in the pulse cycle
            in_cycle = time % pulse_cycle
            if in_cycle < pulse_on:
                # Sine wave with volume amplitude
                value = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq * time))
            else:
                value = 0
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
    print(f"Sucesso! Alarme gerado em {path}")

def generate_yawn_warning(filename, freq1=550, freq2=700, duration_sec=1.5, volume=0.6, sample_rate=44100):
    """
    Generates an alternating two-tone alarm for yawning.
    """
    path = os.path.join("assets", filename)
    num_samples = int(sample_rate * duration_sec)
    
    print(f"Gerando som de bocejo: {path} (Freqs: {freq1}Hz / {freq2}Hz, Duração: {duration_sec}s)")
    with wave.open(path, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            time = i / sample_rate
            # Alternate tone every 0.25 seconds
            freq = freq1 if int(time * 4) % 2 == 0 else freq2
            value = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq * time))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
    print(f"Sucesso! Aviso gerado em {path}")

def generate_distraction_warning(filename, freq1=600, freq2=800, duration_sec=1.5, volume=0.6, sample_rate=44100):
    """
    Generates a rapid pulsing alternating alarm for driver distraction.
    """
    path = os.path.join("assets", filename)
    num_samples = int(sample_rate * duration_sec)
    
    print(f"Gerando som de distracao: {path} (Freqs: {freq1}Hz / {freq2}Hz, Duração: {duration_sec}s)")
    with wave.open(path, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            time = i / sample_rate
            # Rapid pulse: 0.1s beep, 0.1s silent (0.2s cycle)
            in_cycle = time % 0.2
            if in_cycle < 0.1:
                # Alternate frequency between freq1 and freq2
                freq = freq1 if int(time * 5) % 2 == 0 else freq2
                value = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq * time))
            else:
                value = 0
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
    print(f"Sucesso! Alarme de distracao gerado em {path}")

if __name__ == "__main__":
    create_directory()
    # High-pitched urgent alarm for drowsiness
    generate_pulsed_alarm("alarm.wav", freq=900, duration_sec=2.0, volume=0.7, pulse_cycle=0.25, pulse_on=0.12)
    # Dual-tone distinct warning for yawning
    generate_yawn_warning("yawn_warning.wav", freq1=480, freq2=640, duration_sec=1.5, volume=0.6)
    # Rapid-pulse warning for distraction
    generate_distraction_warning("distraction_warning.wav", freq1=650, freq2=850, duration_sec=1.5, volume=0.6)
