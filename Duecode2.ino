#include <Wire.h>
#include <PWFusion_Mcp960x.h>

// Constants
const int NUM_THERMOCOUPLES = 4;
const int DELAY_TIME = 5000; // 5 seconds

// Create an array of sensor objects
Mcp960x thermocouples[NUM_THERMOCOUPLES];

// Thermocouple selection
Mcp960x_Thermocouple_e selectedType;
bool typeSelected = false;

// Variables for non-blocking delay
unsigned long previousMillis = 0;

void initializeThermocouples() {
  uint8_t addresses[] = {0x60, 0x61, 0x64, 0x67};
  for (int i = 0; i < NUM_THERMOCOUPLES; i++) {
    thermocouples[i].begin(addresses[i]);
    if (thermocouples[i].isConnected()) {
      Serial.print(F("Found MCP9601 sensor at address 0x"));
      Serial.println(addresses[i], HEX);

      // Apply selected thermocouple type
      thermocouples[i].setThermocoupleType(selectedType);
      thermocouples[i].setResolution(RES_18BIT, RES_0p0625);
    } else {
      Serial.print(F("ERROR: Unable to connect to MCP9601 sensor at address 0x"));
      Serial.println(addresses[i], HEX);
    }
  }
}

void readAndPrintTemperatures() {
  for (int i = 0; i < NUM_THERMOCOUPLES; i++) {
    Serial.print(F("Thermocouple "));
    Serial.print(i + 1);
    Serial.print(F(" Temp: "));
    switch (thermocouples[i].getStatus()) {
      case OPEN_CIRCUIT:
        Serial.println(F("Open Circuit"));
        break;
      case SHORT_CIRCUIT:
        Serial.println(F("Short Circuit"));
        break;
      case READY:
        Serial.print(thermocouples[i].getThermocoupleTemp());
        Serial.println(F(" °C"));
        break;
      default:
        Serial.println(F("Pending"));
        break;
    }

    Serial.print(F("Ambient Temp: "));
    Serial.print(thermocouples[i].getColdJunctionTemp());
    Serial.println(F(" °C"));
    Serial.println();
  }
}

void setup() {
  Wire.begin();
  Wire.setClock(100000);
  Serial.begin(9600);
  // Wait for serial connection
  while (!Serial);

  Serial.println(F("=== MCP9601 Thermocouple Reader ==="));
  Serial.println(F("Select thermocouple type:"));
  Serial.println(F("1. Type K"));
  Serial.println(F("2. Type J"));
  Serial.println(F("3. Type T"));
  Serial.println(F("4. Type N"));

  // Wait for user to select thermocouple type
  while (!typeSelected) {
    if (Serial.available()) {
      // Small delay to ensure buffer is ready
      delay(10);
      char input = Serial.read();
      // Ignore newline characters
      if (input == '\n' || input == '\r') continue;
      switch (input) {
        case '1': selectedType = TYPE_K; Serial.println(F("Selected: Type K")); typeSelected = true; break;
        case '2': selectedType = TYPE_J; Serial.println(F("Selected: Type J")); typeSelected = true; break;
        case '3': selectedType = TYPE_T; Serial.println(F("Selected: Type T")); typeSelected = true; break;
        case '4': selectedType = TYPE_N; Serial.println(F("Selected: Type N")); typeSelected = true; break;
        default: Serial.println(F("Invalid selection. Enter 1 to 4.")); break;
      }
    }
  }

  // Initialize thermocouples
  initializeThermocouples();
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= DELAY_TIME) {
    previousMillis = currentMillis;

    // Read and print temperatures
    readAndPrintTemperatures();
  }
}
