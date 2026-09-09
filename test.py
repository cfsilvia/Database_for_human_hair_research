from app.importers.excel_reader import read_excel_file


df, metadata = read_excel_file(
    "data/incoming/שאלון1_030926.xlsx")

print(metadata)

print(df.head())