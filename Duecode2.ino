#include <SPI.h>
#include <SD.h>
#include <PlayingWithFusion_MAX31856.h>

// number of thermocouples and their chip select pins
const int numSensors = 4;
int csPins[numSensors] = {4, 5, 6, 7};

// default thermocouple type (changeable at runtime)
max31856_thermocoupletype_t tcType = MAX31856_TCTYPE_K;

// reading interval in milliseconds
unsigned long sampleInterval = 1000;

// SD card chip select pin
const int sdCS = 10;

PlayingWithFusion_MAX31856 sensors[numSensors];
unsigned long lastSample = 0;
File logFile;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nMulti-Thermocouple Reader");
  Serial.println("Commands: TYPE <K/J/T/E/N/S/R/B>, RATE <ms>\n");

  SPI.begin();

  // initialize thermocouples
  for (int i = 0; i < numSensors; i++) {
    sensors[i].begin(csPins[i]);
    sensors[i].setThermocoupleType(tcType);
    sensors[i].setConversionMode(MAX31856_CONTINUOUS);
  }

  // initialize SD card for logging
  if (!SD.begin(sdCS)) {
    Serial.println("SD init failed. Logging disabled.");
  } else {
    Serial.println("SD card ready.");
    logFile = SD.open("temps.csv", FILE_WRITE);
    if (logFile) {
      logFile.println("Time(ms),TC1(C),TC2(C),TC3(C),TC4(C)");
      logFile.flush();
    }
  }
}

void loop() {
  checkSerialCommands();

  if (millis() - lastSample >= sampleInterval) {
    lastSample = millis();
    readAllThermocouples();
  }
}

// read all thermocouples and log results
void readAllThermocouples() {
  Serial.printf("[%lu ms] ", millis());
  String logLine = String(millis());

  for (int i = 0; i < numSensors; i++) {
    float tempC = readThermocouple(i);
    if (!isnan(tempC)) {
      Serial.printf("TC%d: %.2f C  ", i + 1, tempC);
      logLine += "," + String(tempC, 2);
    } else {
      Serial.printf("TC%d: ERROR  ", i + 1);
      logLine += ",ERR";
    }
  }
  Serial.println();

  if (logFile) {
    logFile.println(logLine);
    logFile.flush();
  }
}

// read a single thermocouple with basic fault retry
float readThermocouple(int index) {
  uint8_t fault = sensors[index].readFault();
  if (fault) {
    delay(50);
    fault = sensors[index].readFault();
    if (fault) return NAN;
  }
  return sensors[index].readThermocoupleTemp();
}

// handle runtime serial commands
void checkSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd.startsWith("TYPE ")) {
      char typeChar = cmd.charAt(5);
      setThermocoupleType(typeChar);
    }
    else if (cmd.startsWith("RATE ")) {
      long newRate = cmd.substring(5).toInt();
      if (newRate > 100) {
        sampleInterval = newRate;
        Serial.printf("Sample rate set to %ld ms\n", sampleInterval);
      }
    }
  }
}

// update thermocouple type for all sensors
void setThermocoupleType(char t) {
  max31856_thermocoupletype_t newType;
  switch (t) {
    case 'K': newType = MAX31856_TCTYPE_K; break;
    case 'J': newType = MAX31856_TCTYPE_J; break;
    case 'T': newType = MAX31856_TCTYPE_T; break;
    case 'E': newType = MAX31856_TCTYPE_E; break;
    case 'N': newType = MAX31856_TCTYPE_N; break;
    case 'S': newType = MAX31856_TCTYPE_S; break;
    case 'R': newType = MAX31856_TCTYPE_R; break;
    case 'B': newType = MAX31856_TCTYPE_B; break;
    default:
      Serial.println("Invalid type.");
      return;
  }
  tcType = newType;
  for (int i = 0; i < numSensors; i++) {
    sensors[i].setThermocoupleType(tcType);
  }
  Serial.printf("Type set to %c\n", t);
}
