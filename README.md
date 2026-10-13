# luca-fis-tools

Validate and split journal voucher (yevmiye fişi) import files for **Luca**, the Turkish accounting software, before you upload them.

*Türkçe açıklama aşağıdadır.*

## Why

Luca rejects a voucher import file for small reasons that are hard to spot in a spreadsheet: an empty document number, a trailing dot in an account code, an unbalanced voucher, or too many vouchers in one file. The error shows up only after the upload. This tool finds those problems locally, lists every one with its row number, and can split a large export into parts that fit the import limits.

## What it checks

The input is a CSV with the 14-column Luca voucher layout:

`Fiş No; Fiş Tarihi; Fiş Açıklama; Hesap Kodu; Evrak No; Evrak Tarihi; Detay Açıklama; Borç; Alacak; Miktar; Belge Türü; Para Birimi; Kur; Döviz Tutar`

- exactly 14 columns on every row
- voucher number, account code, document number and both dates are not empty
- dates are valid (`dd.mm.yyyy`, `dd/mm/yyyy` or `yyyy-mm-dd`)
- account codes look like `120.01` (a trailing dot, as in `180.02.`, is reported)
- debit and credit are numbers (`1.234,56` and `1234.56` both work), not negative, and not both filled on one row
- every voucher is balanced (total debit equals total credit)
- a voucher number does not reappear in a separate block
- at most 50 vouchers and 10,000 rows per file

The two limits are what I have seen in my own imports. They are command line options (`--max-vouchers`, `--max-rows`) because they may differ between Luca versions.

## Install

```bash
pip install git+https://github.com/ismailkocaman/luca-fis-tools
```

Python 3.9 or newer, no other dependencies.

## Usage

```bash
# list every problem, exit code 1 if any was found
luca-fis validate fisler.csv

# split into parts that fit the limits; vouchers are never cut in half
luca-fis split fisler.csv --out-dir parcalar/
```

Useful options: `--delimiter ,`, `--encoding cp1254` (Windows-1254 files), `--no-header`.

Try it on the examples:

```bash
luca-fis validate examples/ornek-gecerli.csv
luca-fis validate examples/ornek-hatali.csv
```

The sample data is made up.

## Scope and limits

- CSV only. Excel (`.xls`, `.xlsx`) input is not supported yet.
- This is not an official Luca tool and is not affiliated with it. It checks the rules above, not everything Luca may check.
- Version 0.1. Issues and pull requests are welcome, especially reports of rules this tool misses.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

MIT

---

# Türkçe

**luca-fis-tools**, Luca'ya yükleyeceğiniz yevmiye fişi dosyalarını yüklemeden önce kontrol eder ve gerekirse bölür.

## Neden

Luca, fiş aktarım dosyasını küçük hatalar yüzünden reddedebilir: boş evrak no, hesap kodunun sonunda nokta, dengesiz fiş, dosyada fazla fiş. Hata ancak yükleme sonrasında görünür. Bu araç aynı hataları yerelde bulur, her birini satır numarasıyla listeler ve büyük bir dosyayı limitlere uyan parçalara böler.

## Kontroller

- Her satırda 14 sütun
- Fiş no, hesap kodu, evrak no, fiş tarihi ve evrak tarihi boş değil
- Tarihler geçerli, hesap kodları `120.01` biçiminde (sonda nokta uyarılır)
- Borç/alacak sayı (`1.234,56` ve `1234.56` kabul edilir), negatif değil, aynı satırda ikisi birden dolu değil
- Her fişte toplam borç toplam alacağa eşit
- Aynı fiş numarası dosyada ayrı bloklarda tekrar etmiyor
- Dosya başına en fazla 50 fiş ve 10.000 satır (`--max-vouchers`, `--max-rows` ile değiştirilebilir)

## Kullanım

```bash
pip install git+https://github.com/ismailkocaman/luca-fis-tools

luca-fis validate fisler.csv
luca-fis split fisler.csv --out-dir parcalar/
```

Windows-1254 dosyalar için `--encoding cp1254`, virgül ayraçlı dosyalar için `--delimiter ,` kullanın.

## Kapsam

Şimdilik yalnızca CSV desteklenir. Bu, resmi bir Luca aracı değildir ve Luca ile bağlantısı yoktur. Örnek veriler uydurmadır. Eksik kural bildirimleri ve pull request'ler memnuniyetle karşılanır.

Lisans: MIT
