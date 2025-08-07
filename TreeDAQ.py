import os
import sys
os.add_dll_directory('C:\\Program Files\\Keysight\\IO Libraries Suite\\bin')
import pyvisa
rm = pyvisa.ResourceManager('ktvisa32')
import time
import struct
import matplotlib.pyplot as plt
import numpy as np
import scipy.signal as sig
from datetime import datetime
from datetime import timedelta
import h5py
import yaml
from pymodbus.client import ModbusSerialClient as msc

import logging
from pymodbus.exceptions import ModbusIOException

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
######################################################################################################################
def set_scope_trigger(tek):
    tek.write(""":trig:a:type edge"
                  :trig:auxlevel 0.5;
                  :trig:a:edge:sou aux;
                  :trig:a:edge:slope rise;
                  :trig:a:edge:coupling dc;
                  :trig:a:mode normal;
                  :trig:a:type edge""")
    return

def init_scope_trigger(tek):
    ready_scope(tek)
    return

def ready_scope(tek):
    tek.write("""
              :acquire:mode sample;
              :acquire:seq:numseq 1;
              :acquire:stopafter sequence;
              :acquire:state run; """)
    scope_trig_wait(tek)
    return

def scope_trig_wait(tek):
    for i in range(10):
        tek.query('trig:state?')
        time.sleep(0.1)
        if tek.query('trig:state?') == 'REA\n':
            break

def set_scope_measurements(Tekscope):
    Tekscope.write('measurement:deleteall')

    Tekscope.write('''
                    :measurement:meas1:type base;
                    :measurement:meas2:type top;
                    :measurement:addmeas delay;
                    :measurement:meas3:source1 ch2;
                    :measurement:meas3:source2 ch1;
                    :measurement:meas3:delay:edge1 fall;
                    :measurement:meas3:delay:edge2 fall;
                    :measurement:addmeas delay;
                    :measurement:meas4:source1 ch2;
                    :measurement:meas4:source2 ch1;
                    :measurement:meas4:delay:edge1 rise;
                    :measurement:meas4:delay:edge2 rise;
                    :measurement:meas5:type risetime;
                    :measurement:meas6:type falltime;
                    :measurement:meas7:type povershoot;
                    :measurement:meas8:type novershoot;
                    :measurement:meas9:type mean;
                   ''')

    time.sleep(10)
    return
######################################################################################################################

def impedance_sweep(func_gen, eload, dmm, z_start, z_stop, num_points, compliance):
    # vpp
    voltage_level = 1.0
    # load current
    current_level = compliance

    try:
        func_gen.write(f"freq:start {z_start}")
        func_gen.write(f"freq:stop {z_stop}")
        func_gen.write(f"sweep:points {num_points}")
        func_gen.write(f"volt {voltage_level}")
        func_gen.write(f"init:imm")
        logging.info("Function generator configured for impedance sweep")
    except Exception as e:
        logging.error(f"Error configuring function generator: {e}")
        return None
    
    # set electronic load
    try:
        eload.write("mode curr")
        eload.write(f"curr {current_level}")
        eload.write("input on")
        logging.info("Electronic load configured and turned on")
    except Exception as e:
        logging.error(f"Error configuring electronic load: {e}")
        return None
    
    impedances = []

    try:
        for i in range(num_points):
            freq = z_start + i * (z_stop - z_start) / (num_points - 1)
            func_gen.write(f"freq {freq}")
            time.sleep(0.2)

            voltage = float(dmm.query("meas:volt?"))
            impedance = voltage / current_level
            impedances.append(impedance)

            logging.info(f"Freq: {freq} Hz, Volt: {voltage:.3f} V, Z: {impedance:.2f} Ohm")
    except Exception as e:
        logging.error(f"Error during impedance measurement: {e}")
        # Return whatever has been collected so far
        return impedances
    
    finally:
        try:
            eload.write("input off")
            func_gen.write("*RST")
        except Exception as e:
            logging.warning(f"Error during reset: {e}")

    return impedances    

def smu_volt_sweep(smu, v_start, v_stop, num_points, current_compliance):
    try:
        step_size = (v_stop - v_start) / (num_points - 1)
        smu.write(f'''
          :sour:func:mode volt;
          :sour:volt:mode sweep;
          :sour:volt:start {v_start};
          :sour:volt:stop {v_stop};
          :sour:volt:step {step_size};
          ''')
        # query number of points set
        x = smu.query(':sour:volt:poin?')
        # set up compliance and measurement
        smu.write(f'''
            :sens:func "curr";
            :sens:curr:prot {current_compliance};
            :sens:func "curr";
            :sens:func "volt";
            ''')
        # configure trigger
        smu.write(f'''
            :trig:sour aint;
            :trig:count {x};
            ''')
        # begin sweep
        smu.write('init (@1)')
        # Read measured arrays
        smu_volt_array = smu.query(':fetc:arr:volt? (@1)')
        smu_curr_array = smu.query(':fetc:arr:curr? (@1)')

        # cleanup
        smu.write('sour:volt:mode fix; :sour:volt 0')
        return smu_volt_array, smu_curr_array
    except Exception as e:
        print(f"[ERROR] Voltage sweep failed: {e}")  
        # return partial arrays if available, else empty lists
        return smu_volt_array if 'smu_volt_array' in locals() else [], smu_curr_array if 'smu_curr_array' in locals() else []

def R0_write(relay, addresses, values, retries=5, delay=0.1):

    start_time = time.time()

    if len(addresses) != len(values):
        raise ValueError("Length of addresses and values must match")

    try:
        # read existing state
        for attempt in range(retries):
            read = relay.read_coils(0, 32, 247)
            if not read.isError():
                break
            logging.warning(f"Read attempt {attempt+1} failed, retrying...")
            time.sleep(delay)   
        else:
            raise ModbusIOException("Failed to read relay state after retries")

        codeword = list(read.bits[:32])

        # update targeted addresses
        for addr, val in zip(addresses, values):
            if addr < 0 or addr >= 32:
                raise ValueError(f"Invalid relay address: {addr}")
            codeword[addr] = val

        # write new state
        for attempt in range(retries):
            write = relay.write_coils(0, codeword, 247)
            if not write.isError():
                break
            logging.warning(f"Write attempt {attempt+1} failed, retrying...")
            time.sleep(delay)
        else:
            raise ModbusIOException("Failed to write relay state after retries")

        # confirm write
        for attempt in range(retries):
            verify = relay.read_coils(0, 32, 247)
            if not verify.isError() and list(verify.bits[:32]) == codeword:
                break
            logging.warning(f"Verify attempt {attempt+1} failed, retrying...")
            time.sleep(delay)
        else:
            raise ModbusIOException("Failed to verify relay state after retries")

        elapsed = time.time() - start_time
        logging.info(f"Relay write successful in {elapsed:.3f}s")
        return "R0 write success"

    except ModbusIOException as e:
        logging.error(f"Modbus I/O error: {e}")
        return "R0 write failed (Modbus error)"
    except Exception as e:
        logging.exception(f"Unhandled exception: {e}")
        return "R0 write failed (exception)"
    
def save_data(save_dir, name, data1, data2, data_type):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(save_dir, f"{name}_{data_type}_{timestamp}.h5")
    with h5py.File(filename, "w") as f:
        f.create_dataset("data1", data=[float(d) for d in data2.split(',')])
        if data2:
            f.create_dataset("data2", data=[float(d) for d in data2.split(',')])
        f.attrs["device_name"] = name
        f.attrs["timestamp"] = timestamp
    logging.info(f"Saved data to {filename}")
######################################################################################################################

def safe_shutdown(devices):
    logging.info("Initiating safe shutdown...")
    for dev in devices:
        try:
            if hasattr(dev, 'close'):
                dev.close()
                logging.info(f"{dev} closed successfully.")
        except Exception as e:
            logging.warning(f"Error closing device {dev}: {e}")

def main_loop(smu_devices, tek, smu, dmm, func_gen, eload, R0):
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    save_dir = f"results_{timestamp}"
    os.makedirs(save_dir, exist_ok=True)
    run_summary = {
        "total_devices": len(smu_devices),
        "success": 0,
        "failures": [],
        "partial_data": [],
        "start_time": time.time()
    }

    for device in smu_devices:
        logging.info(f"Beginning test sequence for {device.get('name', 'unknown_device')}")
        try:
            name = device.get("name", "unknown_device")
            input_config = device.get("Input", {})
            output_config = device.get("Output", {})

            logging.info(f"Testing {name} with Input channel {input_config.get('channel',0)} and Output channel {output_config.get('channel', 0)}..")

            # process input config
            if input_config:
                input_channel = input_config.get("channel", 0)
                input_mode = input_config.get("mode", "unkown_mode")
                input_compliance = input_config.get("compliance", 1e-3)

                if input_mode == "volt_sweep":
                    try:
                        v_start = input_config.get("v_start", -0.5)
                        v_stop = input_config.get("v_stop", 1.0)
                        num_points = input_config.get("num_points", 100)
                        voltages, currents = smu_volt_sweep(smu, v_start, v_stop, num_points, input_compliance)
                        device_dir = os.path.join(save_dir, name)
                        os.makedirs(device_dir, exist_ok=True)
                        save_data(device_dir, name, voltages, currents, "iv_data")
                        run_summary["success"] += 1
                    except Exception as e:
                        logging.error(f"Voltage sweep failed for {name}: {e}")
                        run_summary["failures"].append(name)
                        # Save partial data if available
                        if voltages and currents:
                            device_dir = os.path.join(save_dir, name)
                            os.makedirs(device_dir, exist_ok=True)
                            save_data(device_dir, name, voltages, currents, "iv_data_partial")
                            run_summary["partial_data"].append(name)

            # process output config
            if output_config:
                output_channel = input_config.get("channel", 0)
                output_mode = input_config.get("mode", "unkown_mode")
                output_compliance = input_config.get("compliance", 1e-3)

                if output_mode == "impedance_sweep":
                    try:
                        z_start = output_config.get("z_start", 0)
                        z_stop = output_config.get("z_stop", 5)
                        num_points = output_config.get("num_points", 100)
                        impedances = impedance_sweep(func_gen, eload, dmm, z_start, z_stop, num_points, output_compliance)
                        device_dir = os.path.join(save_dir, name)
                        os.makedirs(device_dir, exist_ok=True)
                        save_data(device_dir, name, impedances, None, "impedance_data")
                        run_summary["success"] += 1
                    except Exception as e:
                        logging.error(f"Impedance sweep failed for {name}: {e}")
                        run_summary["failures"].append(name)
                        # Save partial data if available
                        if impedances:
                            device_dir = os.path.join(save_dir, name)
                            os.makedirs(device_dir, exist_ok=True)
                            save_data(device_dir, name, impedances, None, "impedance_data_partial")
                            run_summary["partial_data"].append(name)

        except Exception as e:
            logging.error(f"Error testing device {device.get('name', 'unknown')}: {e}")
            run_summary["failures"].append(device.get('name', 'unknown'))

    run_summary["end_time"] = time.time()
    run_time = run_summary["end_time"] - run_summary["start_time"]
    logging.info("\n===== Test Summary =====")
    logging.info(f"Total devices tested: {run_summary['total_devices']}")
    logging.info(f"Successful runs: {run_summary['success']}")
    logging.info(f"Failures: {run_summary['failures']}")
    logging.info(f"Partial data saved: {run_summary['partial_data']}")
    logging.info(f"Total run time: {run_time:.2f} seconds")
    logging.info("========================")

if __name__ == "__main__":
    # Initialize R0
    R0 = msc(port="COM3", baudrate=9600, timeout=5, retries=10)
    R0.connect()
    logging.info("R0 initialized and connected.")
    print(R0_write(R0, list(range(32)), [False for _ in range(32)]))

    # Initialize resource manager
    rm = pyvisa.ResourceManager()
    logging.info("Resource manager initialized.")

    # Initialize scope
    try:
        tek_scope = rm.open_resource('USB0::0x0699::0x0527::C038286::0::INSTR')
        tek_scope.write_termination = '\n'
        tek_scope.timeout = 10000
        tek_scope.write('*rst')
        tek_scope.write('*cls')
        logging.info(f"Scope initialized: {tek_scope.query('*IDN?').strip()}")
    except pyvisa.errors.VisaIOError as e:
        logging.error(f"Error initializing scope: {e}")

    # Set scope trigger
    set_scope_trigger(tek_scope)
    init_scope_trigger(tek_scope)
    set_scope_measurements(tek_scope)
    tek_scope.write('display:waveview1:ch2:state 1')
    time.sleep(5)

    # Initialize function generator
    try:
        func_gen = rm.open_resource('USB0::0x0957::0x2807::MY62003209::0::INSTR')
        func_gen.write_termination = '\n'
        func_gen.timeout = 5000
        func_gen.write('*rst')
        func_gen.write('*cls')
        logging.info(f"Function generator initialized: {func_gen.query('*IDN?').strip()}")
    except pyvisa.errors.VisaIOError as e:
        logging.error(f"Error initializing function generator: {e}")

    # Initialize SMU
    try:
        smu = rm.open_resource('USB0::0x0957::0xCE18::MY51143560::0::INSTR')
        smu.write_termination = '\n'
        smu.timeout = 10000
        smu.write('*rst')
        smu.write('*cls')
        logging.info(f"SMU initialized: {smu.query('*IDN?').strip()}")
    except pyvisa.errors.VisaIOError as e:
        logging.error(f"Error initializing SMU: {e}")

    # Initialize DMM
    try:
        dmm = rm.open_resource('USB0::0x2A8D::0x1102::MY61006527::0::INSTR')
        dmm.write_termination = '\n'
        dmm.timeout = 5000
        dmm.write('*rst')
        dmm.write('*cls')
        logging.info(f"Power supply initialized: {dmm.query('*IDN?').strip()}")
    except pyvisa.errors.VisaIOError as e:
        logging.error(f"Error initializing power supply: {e}")

    # Initialize electronic load
    try:
        eload = rm.open_resource('USB0::0x2A8D::0x3702::MY61001134::0::INSTR')
        eload.write_termination = '\n'
        eload.timeout = 5000
        eload.write('*rst')
        eload.write('*cls')
        logging.info(f"Electronic load initialized: {eload.query('*IDN?').strip()}")
    except pyvisa.errors.VisaIOError as e:
        logging.error(f"Error initializing electronic load")

    # Import config file
    smu_devices = []

    try:
        with open("tree_DAQ.yml", 'r') as file:
            yaml_docs = yaml.safe_load(file)
            logging.info("YAML file loaded successfully")
            
            # Check if the root element is a dictionary
            if isinstance(yaml_docs, dict):
                smu_devices.append(yaml_docs)
            # else:
            #     print("Warning: Unexpected root element format. Expected a dictionary.")
            
            for dev in smu_devices:
                if 'Input' in dev and 'Output' in dev:
                    print(f"Loaded device {dev['name']} with Input channel {dev['Input']['channel']} and Output channel {dev['Output']['channel']}")
                else:
                    print(f"Warning: Device data missing 'Input' or 'Output' keys: {dev}. Skipping.")
    except yaml.YAMLError as exc:
        print(f"Error reading YAML file: {exc}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    devices = [tek_scope, func_gen, smu, dmm, eload, R0]

    try:
        main_loop(smu_devices, tek_scope, smu, dmm, func_gen, eload, R0)
    except Exception as e:
        print(f"Unhandled error in main loop: {e}")
    finally:
        safe_shutdown(devices)
