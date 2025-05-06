import os, sys, time
import tempfile
import shutil
import zipfile
import unicodedata
import threading, itertools
import yaml

from typing import Final

import logging

logging.basicConfig(
    filename='ootr-music-updater_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

FILES = sys.argv[1:]

# ANSI Terminal Color Codes
RED        : Final = '\x1b[31m'
PINK_218   : Final = '\x1b[38;5;218m'
PINK_204   : Final = '\x1b[38;5;204m'
YELLOW     : Final = '\x1b[33m'
YELLOW_229 : Final = '\x1b[38;5;229m'
CYAN       : Final = '\x1b[36m'
BLUE_39    : Final = '\x1b[38;5;39m'
GRAY_245   : Final = '\x1b[38;5;245m'
GRAY_248   : Final = '\x1b[38;5;248m'
GREEN_79   : Final = '\x1b[38;5;79m'

BOLD      : Final = '\x1b[1m'
ITALIC    : Final = '\x1b[3m'
UNDERLINE : Final = '\x1b[4m'
STRIKE    : Final = '\x1b[9m'
RESET     : Final = '\x1b[0m'

PL  : Final = '\x1b[F'
CL  : Final = '\x1b[K'

SPINNER_FRAMES : Final[list[str]] = [
  "⢀⠀", "⡀⠀", "⠄⠀", "⢂⠀", "⡂⠀", "⠅⠀", "⢃⠀", "⡃⠀",
  "⠍⠀", "⢋⠀", "⡋⠀", "⠍⠁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉",
  "⠋⠉", "⠉⠙", "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⢈⠩", "⡀⢙",
  "⠄⡙", "⢂⠩", "⡂⢘", "⠅⡘", "⢃⠨", "⡃⢐", "⠍⡐", "⢋⠠",
  "⡋⢀", "⠍⡁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉", "⠋⠉", "⠉⠙",
  "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⠈⠩", "⠀⢙", "⠀⡙", "⠀⠩",
  "⠀⢘", "⠀⡘", "⠀⠨", "⠀⢐", "⠀⡐", "⠀⠠", "⠀⢀", "⠀⡀",
]

done_flag = threading.Event()
spinner_thread = threading.Thread()

def spinner_task(message: str, done_flag: threading.Event) -> None:
    for frame in itertools.cycle(SPINNER_FRAMES):
        if done_flag.is_set():
            break
        sys.stderr.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
        sys.stderr.flush()
        time.sleep(0.07)
    sys.stderr.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stderr.flush()

def start_spinner(message: str):
    done_flag.clear()
    thread = threading.Thread(target=spinner_task, args=(message, done_flag))
    thread.start()
    return thread

def remove_diacritics(text: str) -> str:
  '''Normalizes filenames to prevent errors caused by diacritics'''
  normalized = unicodedata.normalize('NFD', text)
  without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

  return without_diacritics

class MusicArchive:
  '''Stores packed music file information, also handling unpacking and repacking'''
  def __init__(self, base_folder, tempfolder):
    self.sequence  : str = None
    self.meta_file : str = None
    self.bank_file : str = None
    self.bankmeta_file : str = None

    # Store zsound filenames
    self.zsounds : list[str] = []

    # Get the paths
    self.basefolder : str = base_folder
    self.tempfolder : str = tempfolder
    self.convfolder : str = os.path.join(self.basefolder, 'converted')

  def unpack(self, filename : str, filepath : str) -> None:
    '''Unpacks an mmrs file into its temp directory'''
    if not os.path.isdir(self.convfolder):
      os.mkdir(self.convfolder)

    with zipfile.ZipFile(filepath, 'r') as zip_archive:
      zip_archive.extractall(self.tempfolder)

    for f in os.listdir(self.tempfolder):
      # Store sequence(s)
      if f.endswith('.seq'):
        self.sequence = f
        continue

      # Sore the zbank and bankmeta information
      if f.endswith('.zbank'):
        self.bank_file = f
        continue

      if f.endswith('.bankmeta'):
        self.bankmeta_file = f
        continue

      # Get the metadata file
      if f.endswith('.meta'):
        self.meta_file = f
        continue

      # Store the zsound information
      if f.endswith('.zsound'):
        self.zsounds.append(f)
        continue

    if not self.sequence:
      raise FileNotFoundError(f'ERROR: Error processing ootrs file: {filename}! Missing sequence file!')
    if not self.meta_file:
      raise FileNotFoundError(f'ERROR: Error processing ootrs file: {filename}! Missing meta file!')

    if self.bank_file and not self.bankmeta_file:
      raise FileNotFoundError(f'ERROR: Error processing ootrs file: {filename}! Missing bankmeta file!')
    if not self.bank_file and self.bankmeta_file:
      raise FileNotFoundError(f'ERROR: Error processing ootrs file: {filename}! Missing zbank file!')

  def pack(self, filename, rel_path) -> None:
    '''Packs the temp folder into a new mmrs file'''
    output_path = os.path.join(self.convfolder, os.path.dirname(rel_path))

    if os.path.exists(output_path) and os.path.isfile(output_path):
      os.remove(output_path)

    os.makedirs(output_path, exist_ok=True)

    archive_path = os.path.join(output_path, filename)
    shutil.make_archive(archive_path, 'zip', self.tempfolder)

    ootrs_path = f'{archive_path}.ootrs'
    if os.path.exists(ootrs_path):
      if os.path.isdir(ootrs_path):
        shutil.rmtree(ootrs_path)
      else:
        os.remove(ootrs_path)

    os.rename(f'{archive_path}.zip', ootrs_path)

def get_files_from_directory(directory: str) -> list[tuple[str, str]]:
  '''Recursively searches a directory to copy its structure'''
  files = []
  for root, _, filenames in os.walk(directory):
    for filename in filenames:
      full_path = os.path.join(root, filename)
      rel_path = os.path.relpath(full_path, start=directory)
      files.append((full_path, rel_path))

  return files

# META OUTPUT
class FlowStyleList(list):
  pass

class HexInt(int):
    pass

def represent_flow_style_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def represent_hexint(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:int', f"0x{data:X}")

yaml.add_representer(FlowStyleList, represent_flow_style_list)
yaml.add_representer(HexInt, represent_hexint)

def write_metadata(folder: str, base_name: str, cosmetic_name: str, meta_bank, song_type: str, categories, zsounds: dict[str, dict[str, int]] = None):
  yaml_dict : dict = {
    "game": "oot",
    "metadata": {
      "display name": cosmetic_name,
      "instrument set": HexInt(meta_bank) if isinstance(meta_bank, int) else meta_bank,
      "song type": song_type,
      "music groups": FlowStyleList([cat for cat in categories]),
    }
  }

  if zsounds:
    yaml_dict["metadata"]["audio samples"] = zsounds

  with open(f"{folder}/{base_name}.meta", "w", encoding="utf-8") as f:
    yaml.dump(yaml_dict, f, sort_keys=False, allow_unicode=True)

def convert_archive(file, base_folder, rel_path) -> None:
  '''Processes and converts an old ootrs file into a new ootrs file'''
  cosmetic_name : str = ''
  meta_bank     : str = ''
  song_type     : str = ''
  categories          = []
  zsounds : dict[str, dict[str, int]] = {}

  #filename = os.path.splitext(os.path.basename((remove_diacritics(file))))[0]
  filename = os.path.splitext(os.path.basename((file)))[0]
  filepath = os.path.abspath(file)

  # Create the temp folder and ensure it deletes itself if an exception occurs
  with tempfile.TemporaryDirectory(prefix='ootrs_convert_') as tempfolder:
    archive = MusicArchive(base_folder, tempfolder)

    # Skip already converted files
    if os.path.isfile(f'{archive.convfolder}/{filename}.ootrs'):
      return

    try:
      archive.unpack(filename, filepath)
    except:
      raise Exception(f'ERROR: Error processing ootrs file: {filename}.ootrs! Cannot unpack archive!')

    meta_name : str = os.path.splitext(os.path.basename(archive.meta_file))[0]

    with open(f'{tempfolder}/{archive.meta_file}', 'r') as meta:
      #lines = io.TextIOWrapper(meta).readlines()
      lines = meta.readlines()
      lines = [line.rstrip() for line in lines]

      cosmetic_name = f"{lines[0]}"
      meta_bank     = "custom" if lines[1] == '-' else int(lines[1], 16)

      if len(lines) < 3:
        song_type = "bgm"
      elif len(lines) >= 3:
        song_type = lines[2].lower()

      if len(lines) >= 4:
        categories = [category for category in lines[3].split(',')]

      # Handle META commands
      if len(lines) >= 5:
        for line in lines[4:]:
          tokens = line.split(':')

          try:
            if tokens[0] == 'ZSOUND':
              zsounds[tokens[4]] = {
                "instrument type": tokens[1],
                "list index": int(tokens[2]),
                "key region": tokens[3] if tokens[3] in ("LOW", "PRIM", "HIGH") else "PRIM"
              }
          except:
            if tokens[0] == 'ZSOUND':
              zsounds[tokens[1]] = {
                "temp address": int(tokens[2], 16)
              }


      with tempfile.TemporaryDirectory(prefix='song_folder_') as song_folder:
        # Copy all files from the tempfolder to song_folder, except the .meta file
        for item in os.listdir(tempfolder):
          if item != archive.meta_file:  # Exclude the meta file
            full_item_path = os.path.join(tempfolder, item)
            if os.path.isfile(full_item_path):
              shutil.copy2(full_item_path, song_folder)

        write_metadata(song_folder, meta_name, cosmetic_name, meta_bank, song_type, categories, zsounds if zsounds else None)

        temp_archive = MusicArchive(base_folder, song_folder)
        temp_archive.pack(f'{filename}', rel_path)

if __name__ == '__main__':
  def process_file(full_path, base_folder, rel_path) -> None:
    '''Processes files and logs any errors that occur during the processing'''
    global spinner_thread
    try:
      if full_path.endswith('.ootrs'):
        convert_archive(full_path, base_folder, rel_path)
    except Exception as e:
      done_flag.set()
      spinner_thread.join()

      print(f"{RED}Error processing {full_path}:{RESET}")
      print(f"{YELLOW}{str(e)}{RESET}")
      logging.error(f"Error processing {full_path}", exc_info=True)

      spinner_thread = start_spinner("Processing files...")

  # Let the user know the process is ongoing
  spinner_thread = start_spinner("Processing files...")

  try:
    for file in FILES:
      # If the path is a directory, get all files and then process them copying directories
      if os.path.isdir(file):
        # DEBUG: Print out which directory is being processed
        # print(f"{CYAN}Processing directory:{RESET} {file}")
        base_folder = os.path.abspath(file)
        file_list = get_files_from_directory(base_folder)

        for full_path, rel_path in file_list:
          # DEBUG: Print out which file in the subdir is being processed
          # print(f"{GRAY_248}  └─ {rel_path}{RESET}")
          process_file(full_path, base_folder, rel_path)

      # If the path is a file, process the file directly
      else:
        # DEBUG: Print out the which file is being processed
        # print(f"{CYAN}Processing file:{RESET} {file}")
        base_folder = os.path.dirname(os.path.abspath(file))
        rel_path = os.path.basename(file)
        full_path = os.path.abspath(file)

        process_file(full_path, base_folder, rel_path)

  # Let the user know the process is over
  finally:
    done_flag.set()
    spinner_thread.join()

    sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    sys.stdout.flush()

  os.system('pause') # Pause so errors and indication the process is complete are not lost
