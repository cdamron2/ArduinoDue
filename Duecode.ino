#include <Wire.h>
#include <PWFusion_Mcp960x.h>

// Create sensor object
Mcp960x thermo1;

// Thermocouple selection
Mcp960x_Thermocouple_e selectedType;
bool typeSelected = false;

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

  // Initialize sensor at I2C address 0x60 (0x60, 0x61, 0x64, or 0x67)
  thermo1.begin(0x60);
  if (thermo1.isConnected()) {
    Serial.println(F("Found MCP9601 sensor"));

    // Apply selected thermocouple type
    thermo1.setThermocoupleType(selectedType);
    thermo1.setResolution(RES_18BIT, RES_0p0625);
  } else {
    Serial.println(F("ERROR: Unable to connect to MCP9601 sensor"));
  }
}

void loop() {
  Serial.print(F("Thermocouple Temp: "));
  switch (thermo1.getStatus()) {
    case OPEN_CIRCUIT:
      Serial.println(F("Open Circuit"));
      break;
    case SHORT_CIRCUIT:
      Serial.println(F("Short Circuit"));
      break;
    case READY:
      Serial.print(thermo1.getThermocoupleTemp());
      Serial.println(F(" °C"));
      break;
    default:
      Serial.println(F("Pending"));
      break;
  }

  Serial.print(F("Ambient Temp: "));
  Serial.print(thermo1.getColdJunctionTemp());
  Serial.println(F(" °C"));
  Serial.println();

  delay(1000);  // 1 second between readings
}
