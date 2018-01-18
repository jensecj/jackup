def print_table(rows):
    """
    Prints out a table using the data in `rows`, which is assumed to be a
    sequence of sequences with the 0th element being the header.
    """

    # figure out column widths
    widths = [ len(max(columns, key=len)) for columns in zip(*rows) ]

    # print header
    header, data = rows[0], rows[1:]
    print(' | '.join( format(title, "%ds" % width) for width, title in zip(widths, header) ))

    # print separator
    print( '-+-'.join( '-' * width for width in widths ) )

    # print data
    for row in data:
        print(" | ".join( format(cdata, "%ds" % width) for width, cdata in zip(widths, row) ))
