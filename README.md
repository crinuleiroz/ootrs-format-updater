# Ocarina of Time Randomizer Music File Updater
This is a python script that copies and updates packed music files (`.ootrs`) to the updated packed format Majora's Mask Randomizer uses that uses a YAML metadata (`.metadata`) file to store metadata.

## 📋 Requirements
This script requires the PyYAML module:
```
pip install pyyaml
```

## 🔧 How To Use
To use this script, follow the steps below:

> 1. Select a folder or file(s) within a folder
> 2. Drag the folder or file(s) onto the script file (`OOTR Music Updater.py`)
> 3. A terminal window will open and display the current file(s) being processed
> 4. After processing, the terminal window will wait for user input before closing

That's it — your files are now copied and converted!

> [!TIP]
> If you would rather see exactly which directories and files are being processed, you can change the `USE_SPINNER` value at the top of the script:
> - True: Prints just the spinner to the terminal
> - False: Prints every directory and file being processed to the terminal

## 📂 Output Folder Location
Converted files are placed in an output folder named `converted`, which is located in the following location depending on the input type:

#### 📁 Folder:
`../path/to/parent_folder/input_folder_converted/`

> [!IMPORTANT]
> When using a folder for input, the directory structure will be preserved. All supported files are converted and placed in their corresponding locations within the `input_folder_converted` folder.
>
> So don't worry — you can safely convert an organized folder without losing its original structure!

#### 📄 File(s):
`../path/to/file_location/converted/`
