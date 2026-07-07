import cv2
import numpy as np
import pandas as pd
import math
import os
import sys
import customtkinter as ctk
from tkinter import messagebox
import traceback
from PIL import ImageTk


def read_linewidths(file):
    csv = pd.read_csv(file, float_precision="round_trip")
    width_col = list(c for c in csv.columns if c.lower() == "width")
    height_col = list(c for c in csv.columns if c.lower() == "height")
    if len(width_col) == 0 or len(height_col) == 0:
        raise RuntimeError("Invalid csv: must have columns labeled 'width' and 'height'.")

    return pd.DataFrame(
        {"width": csv[width_col[0]], "height": csv[height_col[0]]}
    ).apply(pd.to_numeric, errors='raise')
pass


def auto_nm_per_pixel(data):
    width = max(data["width"])
    height = np.ptp(data["height"])

    return round(np.sqrt(width * height / 100_000), 2)
pass

# Gets image dimensions based on width and height of profile


def img_dims(data, nm_per_px):
    width = max(data["width"])
    height = np.ptp(data["height"])

    cal_width = math.ceil(width * (1 / nm_per_px))
    cal_height = math.ceil(height * (1 / nm_per_px))

    return (cal_height, cal_width)


# Gets the coordinates for the image to draw
def get_points(data, cal_height, cal_width, nm_per_px):
    max_height = max(data["height"])
    max_width = max(data["width"])

    # calculated trench height just to have
    # trench_height = min(data.loc[data[col_ls[0]] == width, col_ls[1]]) - min(data.loc[data[col_ls[0]] !=0, col_ls[1]])

    n_data = data.sort_values("height")
    n_heights = n_data["height"]
    n_widths = n_data["width"]

    top_j = n_data["width"].lt(max_width).idxmin()
    height_coord = (max_height - n_heights[np.clip(top_j + 1, 0, len(n_data.index) - 1)]) * (1 / nm_per_px)

    # Bottom of trench calculation no longer necessary but will keep it just in case
    # bot_trench = data.loc[data[col_ls[len(col_ls)-2]] == min(widths), col_ls[len(col_ls)-1]]

    trench_list_x = n_widths[::-1]
    trench_list_y = n_heights[::-1]

    points = [
        [[0, height_coord]], [[0 + cal_width, height_coord]]
    ]

    prev_x = None
    for i, j in zip(trench_list_x, trench_list_y):
        if prev_x is None:
            prev_x = i

        # Original rounding values for reference
        # x1 = round(0 + round((max_width-i)/2), 1)
        # x2 = round((0 + max_width) - round((max_width-i)/2), 1)

        # y = round(max_height - j)

        x1 = (0 + (max_width - i) / 2) * (1 / nm_per_px)
        x2 = ((0 + max_width) - (max_width - i) / 2) * (1 / nm_per_px)

        y = (max_height - j) * (1 / nm_per_px)

        if prev_x == i == max_width:
            prev_x = i
            continue

        points[0].append([x1, y])
        points[0].append([x1, y])
        points[0].append([x1, y])
        points[0].append([x1, y])
        points[1].append([x2, y])
        points[1].append([x2, y])
        points[1].append([x2, y])
        points[1].append([x2, y])

        prev_x = i

    # points[0].append([0, cal_height-(max(bot_trench))])
    # points[1].append([0+cal_width, cal_height-(max(bot_trench))])

    # points[0].append([0, cal_height-(max(bot_trench) *(1/nm_per_px))])
    # points[1].append([0+cal_width, cal_height-(max(bot_trench)*(1/nm_per_px))])

    points[0].append([0, cal_height])
    points[1].append([0 + cal_width, cal_height])

    # return points
    return points


# Creates the image and scales up for ease of viewing
# Saves image as BMP to specified path + /profile.bmp
def create_img(img, points, fname):
    for poly in points:
        cv2.fillPoly(img, np.array([poly], dtype=np.int32), (232, 162, 0))

    # Resize if wanted for viewability
    # scale_percent = 300
    # width = int(img.shape[1] * scale_percent / 100)
    # height = int(img.shape[0] * scale_percent / 100)
    # dim = (width, height)
    # resized = cv2.resize(img, dim, interpolation = cv2.INTER_LINEAR)

    cv2.imwrite(fname, img)

    # Image display on screen
    # cv2.imshow("Trench Profile", img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


class App(ctk.CTk):
    def __init__(self, width=620, height=300):
        super().__init__()

        self.geometry(f"{width}x{height}")
        self.title("Sandbox Studio AI Profile Generation")
        self.minsize(480, 175)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0, 1, 2), weight=1)
        # Set up iconpath
        # self.iconpath = ImageTk.PhotoImage(
        #     file=os.path.join("_internal", "SandBox Studio.ico")
        # )
        # self.wm_iconbitmap()
        # self.iconphoto(False, self.iconpath)

        self.lw_file = None
        self.data = None
        self.output_file = None
        self.nm_per_px = None

        # Linewidth entry
        self.lw_file_entry = ctk.CTkButton(
            self,
            text=". . .",
            width=40,
            command=self.lw_entry_dialog,
        )
        self.lw_file_entry.grid(row=0, column=2, padx=(3, 10))

        self.lw_label = ctk.CTkLabel(self, text="Linewidth File")
        self.lw_label.grid(row=0, column=0, padx=(15, 8))

        self.lw_indicated_file = ctk.StringVar()
        self.lw_filebox = ctk.CTkEntry(
            self, textvariable=self.lw_indicated_file, state=ctk.DISABLED)
        self.lw_filebox.grid(row=0, column=1, padx=2, pady=1, sticky="ew")

        # Output directory entry
        self.output_label = ctk.CTkLabel(self, text="Output File")
        self.output_label.grid(row=1, column=0, padx=(15, 8))

        self.output_indicated_file = ctk.StringVar()
        self.output_filebox = ctk.CTkEntry(
            self, textvariable=self.output_indicated_file, state=ctk.DISABLED)
        self.output_filebox.grid(row=1, column=1, padx=2, pady=1, sticky="ew")

        self.output_entry = ctk.CTkButton(
            self,
            text=". . .",
            width=40,
            command=self.output_entry_dialog,
        )
        self.output_entry.grid(row=1, column=2, padx=(3, 10))

        # Generate profile
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, columnspan=3)

        self.npp_label = ctk.CTkLabel(bottom_frame, text="nm/px:")
        self.npp_label.grid(row=0, column=0, padx=(80, 5), pady=(25, 2))

        self.npp_value = ctk.DoubleVar()
        self.npp_value.trace_add('write', lambda *_: self.update_button_state())
        self.npp_box = ctk.CTkEntry(
            bottom_frame, textvariable=self.npp_value, width=50, justify=ctk.RIGHT)
        self.npp_box.grid(row=0, column=1, padx=(5, 5), pady=(25, 2))

        self.gen_button = ctk.CTkButton(
            bottom_frame,
            text="Generate",
            width=200,
            command=self.gen_button_dialog,
            state=ctk.DISABLED
        )
        self.gen_button.grid(row=0, column=2, padx=(5, 80), pady=(25, 2))
        self.gen_label = ctk.CTkLabel(bottom_frame, text="")
        self.gen_label.grid(row=2, columnspan=4, padx=40, pady=(10, 15), sticky="ew")

    def lw_entry_dialog(self):
        fn = ctk.filedialog.askopenfilename(
            filetypes=(("CSV (Comma delimited)", "*.csv"),)
        )
        if fn == "":
            return

        self.data = read_linewidths(fn)
        self.nm_per_px = auto_nm_per_pixel(self.data)
        self.npp_value.set(self.nm_per_px)
        self.lw_file = fn
        self.lw_indicated_file.set(self.lw_file)
        self.update_button_state()

    def output_entry_dialog(self):
        initialfile = ""
        if self.lw_file is not None:
            initialfile = os.path.splitext(self.lw_file)[0] + ".bmp"

        fn = ctk.filedialog.asksaveasfilename(
            initialfile=initialfile,
            filetypes=(("24-bit Bitmap", "*.bmp"),)
        )
        if fn == "":
            return

        self.output_file = fn
        self.output_indicated_file.set(self.output_file)
        self.update_button_state()

    def update_button_state(self):
        new_state = ctk.DISABLED

        if (self.output_file is None
            or self.data is None
                or self.lw_file is None or not os.path.isfile(self.lw_file)):
            new_state = ctk.DISABLED
        else:
            new_state = ctk.NORMAL

        try:
            self.nm_per_px = self.npp_value.get()
        except Exception:
            new_state = ctk.DISABLED

        self.gen_button.configure(state=new_state)
    pass

    def gen_button_dialog(self):
        if self.lw_file == None or not os.path.isfile(self.lw_file):
            if self.output_file == None or self.output_file == "":
                self.error_window = messagebox.showerror(
                    "Error", "Linewidth file and Output file required")
                return

            self.error_window = messagebox.showerror("Error", "Linewidth file required")
            return

        if self.output_file == None or self.output_file == "":
            if self.lw_file == None or not os.path.isfile(self.lw_file):
                self.error_window = messagebox.showerror(
                    "Error", "Linewidth file and Output file required")
                return

            self.error_window = messagebox.showerror("Error", "Output file required")
            return
        try:
            self.nm_per_px = self.npp_value.get()
        except Exception:
            messagebox.showerror('Invalid value', "nm/px must be a valid number.")
        pass
        img_dim = img_dims(self.data, self.nm_per_px)
        img = np.zeros((img_dim[0], img_dim[1], 3))
        points = get_points(self.data, img_dim[0], img_dim[1], self.nm_per_px)
        create_img(img, points, self.output_file)

        fname = os.path.split(self.output_file)[-1]
        self.gen_label.configure(
            text=f"{fname} successfully generated with nm/px = {self.nm_per_px}."
        )
    pass

    def report_callback_exception(self, *args):
        err = traceback.format_exception(*args)[-1]
        if '_tkinter.TclError' in err:
            return
        messagebox.showerror('Exception', err)

pass


# Users must provide path to output profile and CSV file with widths and heights
# CSV must have widths column before heights column
def main():
    # nm_per_px = 0.05
    # fname = input("Enter linewidth file:")
    # output_path = input("Enter output path:")

    # fname = fname.replace(os.sep, '/')
    # output_path = output_path.replace(os.sep, '/')

    # fname = fname.strip('"')
    # output_path = output_path.strip('"')

    # data = pd.read_csv(fname)

    # img_dim = img_dims(data, nm_per_px)
    # img = np.zeros((img_dim[0], img_dim[1], 3))
    # points = get_points(data, img_dim[0], img_dim[1], nm_per_px)
    # create_img(img, points, output_path)

    ctk.set_appearance_mode("dark")
    app = App()
    if getattr(sys, 'frozen', False):
        import pyi_splash
        pyi_splash.close()

    app.mainloop()

    # print(f"nm/px = {nm_per_px}")
    # print("BMP generated.")
    # print(f"BMP located at {output_path}")

if __name__ == "__main__":
    main()
