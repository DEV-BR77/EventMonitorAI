#include <Arduino.h>
#include <ESP_I2S.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiUdp.h>
#include <esp32-hal-psram.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

#include "secrets.h"

#ifndef EVENTMONITOR_VERSION
#define EVENTMONITOR_VERSION "development"
#define EVENTMONITOR_VERSION_CODE 0
#endif

// INMP441-Verkabelung
constexpr int I2S_PIN_SCK = 5;
constexpr int I2S_PIN_WS = 4;
constexpr int I2S_PIN_SD = 6;

// Audioformat für YAMNet auf dem Raspberry Pi
constexpr uint32_t SAMPLE_RATE = 16000;
constexpr size_t SAMPLES_PER_PACKET = 640;
constexpr uint8_t AUDIO_PROTOCOL_VERSION = 1;

// Raspberry Pi
const IPAddress UDP_TARGET_IP(192, 168, 178, 64);
constexpr uint16_t UDP_TARGET_PORT = 12345;
constexpr uint16_t CLIP_TARGET_PORT = 12346;

#ifndef CLIP_UPLOAD_TOKEN
#error "CLIP_UPLOAD_TOKEN must be configured in include/secrets.h"
#endif

// Das INMP441 liefert 24-Bit-Werte in einem 32-Bit-Slot.
// Shift 14 verstärkt das Signal gegenüber einer reinen 16-Bit-Konvertierung.
constexpr int SAMPLE_SHIFT = 14;
constexpr uint32_t PRE_TRIGGER_SECONDS = 2;
constexpr uint32_t POST_TRIGGER_SECONDS = 3;
constexpr size_t PRE_TRIGGER_SAMPLES = SAMPLE_RATE * PRE_TRIGGER_SECONDS;
constexpr size_t EVENT_CLIP_SAMPLES = SAMPLE_RATE * (PRE_TRIGGER_SECONDS + POST_TRIGGER_SECONDS);
constexpr uint16_t EVENT_TRIGGER_PEAK = 12000;
constexpr uint32_t EVENT_TRIGGER_COOLDOWN_MS = 10000;

I2SClass i2s;
WiFiUDP udp;

int32_t rawSamples[SAMPLES_PER_PACKET];
int16_t pcmSamples[SAMPLES_PER_PACKET];

uint32_t packetsSent = 0;
uint32_t packetSequence = 0;
uint64_t samplesSent = 0;
uint32_t peakSinceReport = 0;
unsigned long lastStatusMs = 0;
unsigned long lastReconnectMs = 0;
int16_t *preTriggerRing = nullptr;
int16_t *eventClip = nullptr;
size_t ringWritePosition = 0;
size_t ringSampleCount = 0;
size_t eventSamplesWritten = 0;
bool eventCaptureActive = false;
volatile bool clipBufferBusy = false;
bool hasTriggered = false;
uint32_t lastTriggerMs = 0;
uint32_t eventSequence = 0;
QueueHandle_t clipQueue = nullptr;

struct __attribute__((packed)) AudioPacketHeader {
    char magic[4];
    uint8_t protocolVersion;
    uint8_t flags;
    uint16_t headerSize;
    uint64_t deviceId;
    uint32_t sequence;
    uint32_t uptimeMs;
    uint16_t sampleRate;
    uint16_t sampleCount;
    uint16_t peak;
    uint16_t firmwareVersionCode;
};

static_assert(sizeof(AudioPacketHeader) == 32, "Unexpected audio packet header size");

struct __attribute__((packed)) WavHeader {
    char riff[4];
    uint32_t fileSizeMinus8;
    char wave[4];
    char fmt[4];
    uint32_t fmtSize;
    uint16_t audioFormat;
    uint16_t channels;
    uint32_t sampleRate;
    uint32_t byteRate;
    uint16_t blockAlign;
    uint16_t bitsPerSample;
    char data[4];
    uint32_t dataSize;
};

static_assert(sizeof(WavHeader) == 44, "Unexpected WAV header size");

struct ClipJob {
    const int16_t *samples;
    size_t sampleCount;
    uint32_t eventId;
    uint32_t triggerUptimeMs;
};

void formatStableDeviceId(char *output, size_t outputSize)
{
    const uint64_t numericId = ESP.getEfuseMac();
    if (outputSize < 19) {
        if (outputSize > 0) {
            output[0] = '\0';
        }
        return;
    }
    memcpy(output, "esp32-", 6);
    for (uint8_t index = 0; index < 6; ++index) {
        snprintf(output + 6 + index * 2, 3, "%02x", static_cast<uint8_t>(numericId >> (index * 8)));
    }
}

WavHeader makeWavHeader(size_t sampleCount)
{
    const uint32_t dataSize = sampleCount * sizeof(int16_t);
    return {
        {'R', 'I', 'F', 'F'},
        36 + dataSize,
        {'W', 'A', 'V', 'E'},
        {'f', 'm', 't', ' '},
        16,
        1,
        1,
        SAMPLE_RATE,
        SAMPLE_RATE * sizeof(int16_t),
        sizeof(int16_t),
        16,
        {'d', 'a', 't', 'a'},
        dataSize,
    };
}

bool uploadClip(const ClipJob &job)
{
    WiFiClient client;
    client.setTimeout(5000);
    if (!client.connect(UDP_TARGET_IP, CLIP_TARGET_PORT, 5000)) {
        return false;
    }

    char deviceId[19];
    formatStableDeviceId(deviceId, sizeof(deviceId));
    const WavHeader header = makeWavHeader(job.sampleCount);
    const size_t contentLength = sizeof(header) + job.sampleCount * sizeof(int16_t);
    client.printf("POST /clips HTTP/1.1\r\n");
    client.printf("Host: %s:%u\r\n", UDP_TARGET_IP.toString().c_str(), CLIP_TARGET_PORT);
    client.printf("Content-Type: audio/wav\r\n");
    client.printf("Content-Length: %u\r\n", static_cast<unsigned int>(contentLength));
    client.printf("X-Clip-Token: %s\r\n", CLIP_UPLOAD_TOKEN);
    client.printf("X-Device-ID: %s\r\n", deviceId);
    client.printf("X-Event-ID: %lu\r\n", static_cast<unsigned long>(job.eventId));
    client.printf(
        "X-Trigger-Uptime-Ms: %lu\r\nConnection: close\r\n\r\n",
        static_cast<unsigned long>(job.triggerUptimeMs)
    );
    if (client.write(reinterpret_cast<const uint8_t *>(&header), sizeof(header)) != sizeof(header)) {
        client.stop();
        return false;
    }
    const uint8_t *payload = reinterpret_cast<const uint8_t *>(job.samples);
    size_t bytesRemaining = job.sampleCount * sizeof(int16_t);
    while (bytesRemaining > 0) {
        const size_t chunkSize = bytesRemaining > 4096 ? 4096 : bytesRemaining;
        const size_t written = client.write(payload, chunkSize);
        if (written == 0) {
            client.stop();
            return false;
        }
        payload += written;
        bytesRemaining -= written;
    }
    const unsigned long responseDeadline = millis() + 5000;
    while (!client.available() && client.connected() && millis() < responseDeadline) {
        delay(10);
    }
    const String statusLine = client.readStringUntil('\n');
    client.stop();
    return statusLine.indexOf(" 201 ") >= 0;
}

void clipSenderTask(void *)
{
    ClipJob job;
    while (true) {
        if (xQueueReceive(clipQueue, &job, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        bool delivered = false;
        for (uint8_t attempt = 1; attempt <= 3 && !delivered; ++attempt) {
            delivered = WiFi.status() == WL_CONNECTED && uploadClip(job);
            if (!delivered) {
                Serial.printf("Clip-Upload #%lu Versuch %u fehlgeschlagen.\n", job.eventId, attempt);
                delay(attempt * 1000);
            }
        }
        Serial.printf(
            "Clip-Upload #%lu %s (%u Samples, 2 s Vorlauf).\n",
            job.eventId,
            delivered ? "erfolgreich" : "endgueltig fehlgeschlagen",
            static_cast<unsigned int>(job.sampleCount)
        );
        clipBufferBusy = false;
    }
}

bool initializeEventBuffer()
{
    if (!psramFound()) {
        Serial.println("WARNUNG: Keine PSRAM erkannt; Ereignisclips deaktiviert.");
        return false;
    }
    preTriggerRing = static_cast<int16_t *>(ps_malloc(PRE_TRIGGER_SAMPLES * sizeof(int16_t)));
    eventClip = static_cast<int16_t *>(ps_malloc(EVENT_CLIP_SAMPLES * sizeof(int16_t)));
    clipQueue = xQueueCreate(1, sizeof(ClipJob));
    if (!preTriggerRing || !eventClip || !clipQueue) {
        Serial.println("WARNUNG: PSRAM-Ringpuffer konnte nicht angelegt werden.");
        return false;
    }
    memset(preTriggerRing, 0, PRE_TRIGGER_SAMPLES * sizeof(int16_t));
    xTaskCreatePinnedToCore(clipSenderTask, "clip-uploader", 8192, nullptr, 1, nullptr, 0);
    Serial.printf(
        "PSRAM-Ereignispuffer aktiv: %u s Vorlauf + %u s Nachlauf (%u Bytes).\n",
        PRE_TRIGGER_SECONDS,
        POST_TRIGGER_SECONDS,
        static_cast<unsigned int>((PRE_TRIGGER_SAMPLES + EVENT_CLIP_SAMPLES) * sizeof(int16_t))
    );
    return true;
}

void addToPreTriggerRing(const int16_t *samples, size_t sampleCount)
{
    if (!preTriggerRing) {
        return;
    }
    for (size_t i = 0; i < sampleCount; ++i) {
        preTriggerRing[ringWritePosition] = samples[i];
        ringWritePosition = (ringWritePosition + 1) % PRE_TRIGGER_SAMPLES;
        if (ringSampleCount < PRE_TRIGGER_SAMPLES) {
            ++ringSampleCount;
        }
    }
}

void startEventCapture(uint32_t triggerUptimeMs)
{
    if (!eventClip || eventCaptureActive || clipBufferBusy) {
        return;
    }
    const size_t padding = PRE_TRIGGER_SAMPLES - ringSampleCount;
    memset(eventClip, 0, padding * sizeof(int16_t));
    const size_t oldest = (ringWritePosition + PRE_TRIGGER_SAMPLES - ringSampleCount)
        % PRE_TRIGGER_SAMPLES;
    for (size_t i = 0; i < ringSampleCount; ++i) {
        eventClip[padding + i] = preTriggerRing[(oldest + i) % PRE_TRIGGER_SAMPLES];
    }
    eventSamplesWritten = PRE_TRIGGER_SAMPLES;
    eventCaptureActive = true;
    clipBufferBusy = true;
    lastTriggerMs = triggerUptimeMs;
    hasTriggered = true;
    ++eventSequence;
    Serial.printf("Ereignistrigger #%lu bei Peak >= %u.\n", eventSequence, EVENT_TRIGGER_PEAK);
}

void appendEventSamples(const int16_t *samples, size_t sampleCount)
{
    if (!eventCaptureActive) {
        return;
    }
    const size_t remaining = EVENT_CLIP_SAMPLES - eventSamplesWritten;
    const size_t copyCount = sampleCount < remaining ? sampleCount : remaining;
    memcpy(eventClip + eventSamplesWritten, samples, copyCount * sizeof(int16_t));
    eventSamplesWritten += copyCount;
    if (eventSamplesWritten == EVENT_CLIP_SAMPLES) {
        eventCaptureActive = false;
        const ClipJob job = {eventClip, EVENT_CLIP_SAMPLES, eventSequence, lastTriggerMs};
        if (xQueueSend(clipQueue, &job, 0) != pdTRUE) {
            Serial.println("WARNUNG: Clip-Upload-Warteschlange ist belegt.");
            clipBufferBusy = false;
        }
    }
}

void connectWiFi()
{
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(false);

    Serial.printf("Verbinde mit WLAN: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.println("WLAN verbunden");
    Serial.print("ESP32-IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("UDP-Ziel: ");
    Serial.print(UDP_TARGET_IP);
    Serial.print(":");
    Serial.println(UDP_TARGET_PORT);
}

bool startI2S()
{
    // BCLK, WS, DOUT (nicht verwendet), DIN
    i2s.setPins(I2S_PIN_SCK, I2S_PIN_WS, -1, I2S_PIN_SD);

    const bool started = i2s.begin(
        I2S_MODE_STD,
        SAMPLE_RATE,
        I2S_DATA_BIT_WIDTH_32BIT,
        I2S_SLOT_MODE_MONO
    );

    if (!started) {
        Serial.println("FEHLER: I2S konnte nicht gestartet werden.");
        return false;
    }

    Serial.println("I2S gestartet:");
    Serial.printf(
        "  SCK=GPIO%d, WS=GPIO%d, SD=GPIO%d\n",
        I2S_PIN_SCK,
        I2S_PIN_WS,
        I2S_PIN_SD
    );
    Serial.printf("  %lu Hz, 32-Bit Eingang, linker Mono-Kanal\n", SAMPLE_RATE);

    return true;
}

void setup()
{
    Serial.begin(115200);
    delay(1500);

    Serial.println();
    Serial.println("EventMonitorAI ESP32-S3 UDP Audio");
    Serial.printf("Version %s\n", EVENTMONITOR_VERSION);
    Serial.println("--------------------------------");

    connectWiFi();

    if (!udp.begin(0)) {
        Serial.println("FEHLER: UDP konnte nicht gestartet werden.");
        while (true) {
            delay(1000);
        }
    }

    if (!startI2S()) {
        while (true) {
            delay(1000);
        }
    }

    initializeEventBuffer();

    Serial.println("Audiostream aktiv.");
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED) {
        const unsigned long now = millis();

        if (now - lastReconnectMs >= 5000) {
            lastReconnectMs = now;
            Serial.println("WLAN getrennt – neuer Verbindungsversuch.");
            WiFi.reconnect();
        }

        delay(20);
        return;
    }

    const size_t bytesRead = i2s.readBytes(
        reinterpret_cast<char *>(rawSamples),
        sizeof(rawSamples)
    );

    const size_t sampleCount = bytesRead / sizeof(int32_t);

    if (sampleCount == 0) {
        delay(1);
        return;
    }

    uint32_t packetPeak = 0;
    for (size_t i = 0; i < sampleCount; ++i) {
        int32_t sample = rawSamples[i] >> SAMPLE_SHIFT;

        if (sample > 32767) {
            sample = 32767;
        } else if (sample < -32768) {
            sample = -32768;
        }

        pcmSamples[i] = static_cast<int16_t>(sample);

        const uint32_t absoluteSample =
            sample >= 0
                ? static_cast<uint32_t>(sample)
                : static_cast<uint32_t>(-sample);

        if (absoluteSample > peakSinceReport) {
            peakSinceReport = absoluteSample;
        }
        if (absoluteSample > packetPeak) {
            packetPeak = absoluteSample;
        }
    }

    AudioPacketHeader header = {
        {'E', 'M', 'A', 'I'},
        AUDIO_PROTOCOL_VERSION,
        0,
        sizeof(AudioPacketHeader),
        ESP.getEfuseMac(),
        packetSequence++,
        millis(),
        SAMPLE_RATE,
        static_cast<uint16_t>(sampleCount),
        static_cast<uint16_t>(packetPeak > 32767 ? 32767 : packetPeak),
        EVENTMONITOR_VERSION_CODE,
    };

    const uint32_t now = millis();
    const bool cooldownFinished = !hasTriggered || now - lastTriggerMs >= EVENT_TRIGGER_COOLDOWN_MS;
    if (
        packetPeak >= EVENT_TRIGGER_PEAK
        && cooldownFinished
        && ringSampleCount == PRE_TRIGGER_SAMPLES
    ) {
        startEventCapture(now);
    }
    appendEventSamples(pcmSamples, sampleCount);
    addToPreTriggerRing(pcmSamples, sampleCount);

    if (udp.beginPacket(UDP_TARGET_IP, UDP_TARGET_PORT)) {
        udp.write(reinterpret_cast<const uint8_t *>(&header), sizeof(header));
        udp.write(
            reinterpret_cast<const uint8_t *>(pcmSamples),
            sampleCount * sizeof(int16_t)
        );

        if (udp.endPacket() == 1) {
            ++packetsSent;
            samplesSent += sampleCount;
        }
    }

    if (now - lastStatusMs >= 2000) {
        lastStatusMs = now;

        Serial.printf(
            "UDP-Pakete=%lu | Samples=%llu | Peak=%lu | Ziel=%s:%u\n",
            packetsSent,
            samplesSent,
            peakSinceReport,
            UDP_TARGET_IP.toString().c_str(),
            UDP_TARGET_PORT
        );

        peakSinceReport = 0;
    }
}
