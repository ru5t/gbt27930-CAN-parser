from decimal import Decimal
import argparse
import binascii
import csv
import json
import time

mul_frame_id = ["CEC56F4", "CECF456", "CEB56F4", "CECF456"]
addr = ["56", "F4"]
mul_frame_pgn = None
mul_frame_data = ""
mul_frame_num = None
mul_frame_byte = None
mul_frame_first = None

def format_data(data):
    data = data.split(" ")[-1]
    data = data.split("#")
    ci = data[0]
    cd = data[-1]
    return ci, cd

def get_pgn(ci):
    p = "00" + ci[2:4] + "00"
    p = int(p, 16)
    return str(p)
    #return f"0x {ci[2:4]}"

def orientation(ci):
    da = ci[4:6]
    sa = ci[6:]
    if sa in addr:
        if sa == addr[0]:
            sa = "Charger"
        else:
            sa = "BMS"
    else:
        sa = "???"
    if da in addr:
        if da == addr[0]:
            da = "Charger"
        else:
            da = "BMS"
    else:
        da = "???"

    return f"{sa}-{da}\t"

def pgn_message(p, pj):
    m = ""
    if p in pj:
        for k in pj[p]:
            m += f"{pj[p][k]}\t"
    return m

def pgn_content(p, cd):
    c = ""
    with open("SPN.json", "r", encoding="utf-8") as f:
        spn_json = json.load(f)
    for sl in spn_json[p]:
        if sl["process_mode"] == "select":
            if isinstance(sl["start_byte_or_bit"], int):
                d = cd[(sl["start_byte_or_bit"] - 1) * 2:(sl["start_byte_or_bit"] + sl["length"] - 1) * 2]
                if d:
                    d = (bytes.fromhex(d)[::-1].hex()).upper()
                    if d in sl["definition_data"]:
                        c += f'{sl["content"][sl["definition_data"].index(d)]};'
            else:
                if sl["length"] >= 8:
                    if sl["length"] % 8 == 0:
                        n = int(sl["length"] / 8 + sl["start_byte_or_bit"])
                    else:
                        n = int(sl["length"] / 8 + sl["start_byte_or_bit"]) + 1
                else:
                    n = int(sl["start_byte_or_bit"])
                d = cd[int(sl["start_byte_or_bit"] - 1) * 2:n * 2]
                if d:
                    d = (bytes.fromhex(d)[::-1].hex()).upper()
                    db = bin(int(binascii.hexlify(bytes.fromhex(d)), 16))[2:].zfill(8 * (n - int(sl["start_byte_or_bit"]) + 1))
                    sb = int(str(sl["start_byte_or_bit"]).split('.')[1]) - 1
                    eb = sb + sl["length"] + 1
                    if sb == 0:
                        eb = eb - 1
                    section = db[sb:eb]
                    try:
                        c += f'{sl["content"][sl["definition_data"].index(section)]}; '
                    except ValueError:
                        c += f'Parsing error: standard does not define meaning for {section};'
        elif sl["process_mode"] == "ascii":
            if isinstance(sl["start_byte_or_bit"], int):
                d = cd[(sl["start_byte_or_bit"] - 1) * 2:(sl["start_byte_or_bit"] + sl["length"] - 1) * 2]
                if d:
                    ascii_string = ''.join(chr(int(d[i:i + 2], 16)) for i in range(0, len(d), 2))
                    c += f'{sl["content"]}{ascii_string};'
        elif sl["process_mode"] == "calculate":
            if isinstance(sl["start_byte_or_bit"], int):
                d = cd[(sl["start_byte_or_bit"] - 1) * 2:(sl["start_byte_or_bit"] + sl["length"] - 1) * 2]
                if d:
                    d = (bytes.fromhex(d)[::-1].hex()).upper()
                    result = Decimal(str(sl["data_resolution"])) * Decimal(int(d, 16)) + sl["offset"]
                    if result < 0:
                        result = abs(result)
                    c += f'{sl["content"]}{result}{sl["units"]};'
            else:
                if sl["length"] >= 8:
                    if sl["length"] % 8 == 0:
                        n = int(sl["length"] / 8 + sl["start_byte_or_bit"])
                    else:
                        n = int(sl["length"] / 8 + sl["start_byte_or_bit"])
                else:
                    n = int(sl["start_byte_or_bit"])
                d = cd[int(sl["start_byte_or_bit"] - 1) * 2:n * 2]
                if d:
                    db = bin(int(binascii.hexlify(bytes.fromhex(d)), 16))[2:].zfill(8 * (n - int(sl["start_byte_or_bit"]) + 1))
                    sb = int(str(sl["start_byte_or_bit"]).split('.')[1]) - 1
                    eb = sb + sl["length"] + 1
                    if sb == 0:
                        eb = eb - 1
                    section = db[sb:eb]
                    result = Decimal(str(sl["data_resolution"])) * Decimal(int(section, 2)) + sl["offset"]
                    if result < 0:
                        result = abs(result)
                    c += f'{sl["content"]}{result}{sl["units"]};'
        elif sl["process_mode"] == "date":
            if isinstance(sl["start_byte_or_bit"], int):
                d = cd[(sl["start_byte_or_bit"] - 1) * 2:(sl["start_byte_or_bit"] + sl["length"] - 1) * 2]
                if d:
                    if sl["SPN"] == "2571":
                        year = int(d[0:2], 16) + 1985
                        month = int(d[2:4], 16)
                        day = int(d[4:6], 16)
                        c += f'{sl["content"]}{year}-{month:02d}-{day:02d};'
                    elif sl["SPN"] == "2576":
                        year = int((bytes.fromhex(d[4:8])[::-1].hex()).upper(), 16)
                        month = int(d[2:4], 16)
                        day = int(d[0:2], 16)
                        c += f'{sl["content"]}{year}-{month:02d}-{day:02d};'
                    elif sl["SPN"] == "2823":
                        year = (bytes.fromhex(d[10:14])[::-1].hex()).upper()
                        month = d[8:10]
                        day = d[6:8]
                        hour = d[4:6]
                        minute = d[2:4]
                        second = d[0:2]
                        c += f'{sl["content"]}{year}-{month}-{day} {hour}:{minute}:{second};'
        elif sl["process_mode"] == "null":
            if isinstance(sl["start_byte_or_bit"], int):
                d = cd[(sl["start_byte_or_bit"] - 1) * 2:(sl["start_byte_or_bit"] + sl["length"] - 1) * 2]
                if d:
                    c += f'{sl["content"]}, frame data is {d};'
    return c

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse candump log or file with each line as \"can_id#can_data\" according to GB/T 27930-2015")
    parser.add_argument("-f", "--file", help="Specify the file path to process")

    args = parser.parse_args()

    header = ["Frame Number", "Frame ID", "Phase", "PGN", "Message Code", "Message Description", "Priority", "Source Address-Destination Address", "Frame Length", "Frame Data",
              "Frame Data Meaning"]
    print("\t".join(header))

    t = time.strftime('%Y-%m-%d_%H%M%S', time.localtime())

    with open(f"analysis-{t}.csv", "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, escapechar='\\', quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(header)

        with open(args.file, "r", encoding="utf-8") as file1:
            with open("PGN.json", "r", encoding="utf-8") as pgn_file:
                pgn_json = json.load(pgn_file)
            line_num = 0

            for line in file1:
                content = ""
                line = line.strip()
                if line:
                    can_id, can_data = format_data(line)
                    data_len = f"{str(int(len(can_data) / 2))}\t"
                    pgn = get_pgn(can_id)
                    o = orientation(can_id)

                    if pgn in pgn_json:
                        message = f"{str(line_num)}\t0x{can_id}\t"
                        pm = pgn_message(pgn, pgn_json)
                        message += f"{pm}{o}{data_len}0x{can_data}\t"

                        content = pgn_content(pgn, can_data)
                        mc = message + content
                        print(mc)
                        writer.writerow(mc.split("\t"))
                    elif can_id[1:] in mul_frame_id:
                        pgn = str(int(can_data[10:], 16))
                        message = f"{str(line_num)}\t0x{can_id}\t"
                        pm = pgn_message(pgn, pgn_json)
                        message += f"{pm}{o}{data_len}0x{can_data}\t"

                        if can_data[0:2] == "10":
                            byte_num = str(int(can_data[2:4], 16))
                            frame_num = str(int(can_data[6:8], 16))
                            mul_frame_byte = byte_num
                            mul_frame_num = frame_num
                            content = f"Multi-frame send request frame, total bytes {byte_num}, total frames to send {frame_num}"
                            mc = message + content

                            print(mc)
                            writer.writerow(mc.split("\t"))
                        elif can_data[0:2] == "11":
                            frame_num = str(int(can_data[2:4], 16))
                            first_frame = can_data[4:6]
                            mul_frame_first = 0
                            mul_frame_pgn = pgn
                            content = f"Multi-frame request response frame, sendable frames {frame_num}, first frame number of multi-frame send {first_frame}"
                            mc = message + content

                            print(mc)
                            writer.writerow(mc.split("\t"))
                        elif can_data[0:2] == "13":
                            receive_byte_num = int(can_data[2:4], 16)
                            receive_frame_num = int(can_data[6:8], 16)
                            content = f"Multi-frame receive complete frame, received total bytes {receive_byte_num}, received total frames {receive_frame_num};\nMulti-frame parsing result: 【"

                            mul_frame_data = mul_frame_data[0:receive_byte_num * 2]

                            content += pgn_content(mul_frame_pgn, mul_frame_data) + "】"
                            mc = message + content

                            print(mc)
                            writer.writerow(mc.split("\t"))
                            mul_frame_pgn = None
                            mul_frame_data = ""
                            mul_frame_num = None
                            mul_frame_byte = None
                            mul_frame_first = None
                        elif can_data[0] == "0":
                            mul_frame_data += can_data[2:]
                            mul_frame_first += 1

                            message = f"{str(line_num)}\t0x{can_id}\t"
                            pm = pgn_message(mul_frame_pgn, pgn_json)
                            message += f"{pm}{o}{data_len}0x{can_data}\t"
                            content = f"Multi-frame send frame #{mul_frame_first}"
                            mc = message + content

                            print(mc)
                            writer.writerow(mc.split("\t"))
                    else:
                        mc = f"{str(line_num)}\t0x{can_id}\t-\t-\t-\t-\t-\t{o}{data_len}0x{can_data}\t-"
                        print(mc)
                        writer.writerow(mc.split("\t"))
                    line_num += 1