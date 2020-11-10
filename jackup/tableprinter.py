def print_table(rows):
    # figure out column widths
    widths = [len(max(columns, key=len)) for columns in zip(*rows)]

    # print header
    header, data = rows[0], rows[1:]
    headings = [format(title, f"{width}s") for width, title in zip(widths, header)]
    print(" | ".join(headings))

    # print header separator
    print("-+-".join("-" * width for width in widths))

    # print data
    for row in data:
        cols = [format(cdata, "%ds" % width) for width, cdata in zip(widths, row)]
        print(" | ".join(cols))
