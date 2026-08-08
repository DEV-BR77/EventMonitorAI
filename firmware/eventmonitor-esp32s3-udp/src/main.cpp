#include <Arduino.h>
#include <ESP_I2S.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "secrets.h"

#ifndef EVENTMONITOR_VERSION
#define EVENTMONITOR_VERSION "development"
#endif

// INMP441-Verkabelung
constexpr int I2S_PIN_SCK = 5;
constexpr int I2S_PIN_WS = 4;
constexpr int I2S_PIN_SD = 6;

// Audioformat für YAMNet auf dem Raspberry Pi
constexpr uint32_t SAMPLE_RATE = 16000;
constexpr size_t SAMPLES_PER_PACKET = 640;

// Raspberry Pi
const IPAddress UDP_TARGET_IP(192, 168, 178, 64);
constexpr uint16_t UDP_TARGET_PORT = 12345;

// Das INMP441 liefert 24-Bit-Werte in einem 32-Bit-Slot.
// Shift 14 verstärkt das Signal gegenüber einer reinen 16-Bit-Konvertierung.
constexpr int SAMPLE_SHIFT = 14;

I2SClass i2s;
WiFiUDP udp;

int32_t rawSamples[SAMPLES_PER_PACKET];
int16_t pcmSamples[SAMPLES_PER_PACKET];

uint32_t packetsSent = 0;
uint64_t samplesSent = 0;
uint32_t peakSinceReport = 0;
unsigned long lastStatusMs = 0;
unsigned long lastReconnectMs = 0;

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
    }

    if (udp.beginPacket(UDP_TARGET_IP, UDP_TARGET_PORT)) {
        udp.write(
            reinterpret_cast<const uint8_t *>(pcmSamples),
            sampleCount * sizeof(int16_t)
        );

        if (udp.endPacket() == 1) {
            ++packetsSent;
            samplesSent += sampleCount;
        }
    }

    const unsigned long now = millis();

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
