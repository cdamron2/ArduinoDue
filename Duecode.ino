#include <Wire.h>
#include <PWFusion_Mcp960x.h>

Mcp960x thermo1;

int selectedType = -1;

void setup() {
  // Start I2C and Serial
  Wire.begin();
  Wire.setClock(100000);
  Serial.begin(9600);
  while (!Serial); // Wait for Serial Monitor to open

  Serial.println(F("=== MCP9601 Thermocouple Reader ==="));
  Serial.println(F("Select thermocouple type:"));
  Serial.println(F("1. Type K"));
  Serial.println(F("2. Type J"));
  Serial.println(F("3. Type T"));
  Serial.println(F("4. Type N"));

  // Wait for valid selection
  while (selectedType == -1) {
    if (Serial.available()) {
      char input = Serial.read();
      switch (input) {
        case '1': selectedType = TYPE_K; Serial.println(F("Selected: Type K")); break;
        case '2': selectedType = TYPE_J; Serial.println(F("Selected: Type J")); break;
        case '3': selectedType = TYPE_T; Serial.println(F("Selected: Type T")); break;
        case '4': selectedType = TYPE_N; Serial.println(F("Selected: Type N")); break;
        default: Serial.println(F("Invalid selection. Enter 1–4.")); break;
      }
    }
  }

  // Init MCP9601 at I2C address 1
  thermo1.begin(1);
  if (thermo1.isConnected()) {
    Serial.println(F("Found MCP9601 sensor"));
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
  delay(1000);
}
