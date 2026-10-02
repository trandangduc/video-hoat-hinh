"""Run without arguments for GUI; use --help for folder/ZIP command line mode."""
from __future__ import annotations
import argparse
import getpass
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath
from cryptography.exceptions import InvalidTag
from xvideo import decrypt, parse_key


def run(source, output, key_text, report=print):
    source, output = Path(source).resolve(), Path(output).resolve()
    key = parse_key(key_text)
    if not source.exists():
        raise ValueError('Không tìm thấy thư mục / file nguồn.')
    with tempfile.TemporaryDirectory(prefix='xvideo-zip-') as tmp:
        if source.is_file() and source.suffix.lower() == '.zip':
            root = Path(tmp)
            with zipfile.ZipFile(source) as z:
                seen = set()
                for entry in z.infolist():
                    name = PurePosixPath(entry.filename)
                    if '\\' in entry.filename or name.is_absolute() or '..' in name.parts or ':' in entry.filename:
                        raise ValueError('ZIP chứa đường dẫn không an toàn.')
                    if entry.is_dir() or name.suffix.lower() != '.brd':
                        continue
                    if name.as_posix().casefold() in seen:
                        raise ValueError('ZIP chứa tên file trùng.')
                    seen.add(name.as_posix().casefold())
                    dest = root.joinpath(*name.parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(entry) as inp, dest.open('xb') as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
            files = sorted(root.rglob('*.brd'))
        elif source.is_dir():
            root, files = source, sorted(source.rglob('*.brd'))
        elif source.suffix.lower() == '.brd':
            root, files = source.parent, [source]
        else:
            raise ValueError('Chọn thư mục, file .brd hoặc ZIP.')
        if not files:
            raise ValueError('Không tìm thấy file .brd.')
        for file in files:
            target = output / file.relative_to(root).with_suffix('.mp4')
            if target.exists():
                raise ValueError(f'File đã tồn tại, hãy chọn thư mục đích khác: {target}')
        for i, file in enumerate(files, 1):
            try:
                dest = decrypt(file, output / file.relative_to(root).with_suffix('.mp4'), key)
            except InvalidTag as e:
                raise ValueError(f'Sai key hoặc file bị thay đổi: {file.name}. Không xuất MP4 lỗi.') from e
            report(f'{i}/{len(files)}: {dest}')
    return len(files)


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    window = tk.Tk()
    window.title('Giải mã BRD → MP4')
    window.geometry('730x410')
    source, output, secret = tk.StringVar(), tk.StringVar(), tk.StringVar()
    box = ttk.Frame(window, padding=20)
    box.pack(fill='both', expand=True)
    box.columnconfigure(0, weight=1)
    ttk.Label(box, text='1. Chọn thư mục .brd hoặc file ZIP đã tải').grid(row=0, column=0, sticky='w')
    ttk.Entry(box, textvariable=source).grid(row=1, column=0, sticky='ew', pady=8)
    ttk.Button(box, text='Thư mục', command=lambda: source.set(filedialog.askdirectory() or source.get())).grid(row=1, column=1)
    ttk.Button(box, text='File / ZIP', command=lambda: source.set(filedialog.askopenfilename(filetypes=[('BRD / ZIP', '*.brd *.zip')]) or source.get())).grid(row=1, column=2)
    ttk.Label(box, text='2. Chọn thư mục lưu MP4').grid(row=2, column=0, sticky='w')
    ttk.Entry(box, textvariable=output).grid(row=3, column=0, sticky='ew', pady=8)
    ttk.Button(box, text='Chọn nơi lưu', command=lambda: output.set(filedialog.askdirectory() or output.get())).grid(row=3, column=1, columnspan=2)
    ttk.Label(box, text='3. Nhập key hoặc mở file video.key').grid(row=4, column=0, sticky='w')
    ttk.Entry(box, textvariable=secret, show='*').grid(row=5, column=0, sticky='ew', pady=8)
    def load():
        p = filedialog.askopenfilename(title='Chọn video.key')
        if p:
            try:
                secret.set(Path(p).read_text().strip())
            except Exception as e:
                messagebox.showerror('Không đọc được key', str(e))
    ttk.Button(box, text='Mở key', command=load).grid(row=5, column=1, columnspan=2)
    status = tk.StringVar(value='Key được xử lý tại máy của bạn, không gửi lên mạng.')
    ttk.Label(box, textvariable=status, wraplength=670).grid(row=7, column=0, columnspan=3, sticky='w', pady=16)
    def start():
        values = source.get(), output.get(), secret.get()
        if not all(values):
            messagebox.showerror('Thiếu thông tin', 'Cần nguồn, thư mục đích và key.')
            return
        button.config(state='disabled')
        def work():
            try:
                n = run(*values, report=lambda s: window.after(0, status.set, s))
                window.after(0, status.set, f'Đã giải mã {n} video thành MP4.')
            except Exception as e:
                window.after(0, messagebox.showerror, 'Giải mã thất bại', str(e))
            finally:
                window.after(0, button.config, {'state': 'normal'})
        threading.Thread(target=work, daemon=True).start()
    button = ttk.Button(box, text='Giải mã thành MP4', command=start)
    button.grid(row=6, column=0, sticky='w', pady=8)
    window.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Giải mã thư mục BRD / ZIP thành MP4. Không ghi đè file có sẵn.')
    parser.add_argument('source', nargs='?')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--key-file', type=Path)
    args = parser.parse_args()
    if not args.source:
        gui()
    else:
        if not args.output:
            parser.error('Cần --output THU_MUC_DICH')
        try:
            key_text = args.key_file.read_text().strip() if args.key_file else getpass.getpass('Nhập key: ')
            print(f'Hoàn thành: {run(args.source, args.output, key_text)} file.')
        except Exception as e:
            parser.exit(1, f'Lỗi: {e}\n')
