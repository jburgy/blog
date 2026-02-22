row = "<tr><th>{}</th>{}</tr>".format
cell = (
    '<td><input type="text" required minlength=1 maxlength=3'
    ' size=1 pattern={}></td>'.format
)

if __name__ == "__main__":
  print(
      """<html lang="en">
    <head>
      <title>Multiplication Table</title>
    </head>
    <style>
    input:invalid {{ color: #c00; }}
    </style>
    <body>
      <table>
        <thead>
          <tr>
          <th>&times;</th>
          {}
          </tr>
        </thead>
        <tbody>
        {}
        </tbody>
      </table>
    </body>
  </html>
  """.format(
          "\n".join(f"<th>{i}</th>" for i in range(1, 13)),
          "\n".join(
              row(i, "\n".join(cell(i * j) for j in range(1, 13))) for i in range(1, 13)
          ),
      )
  )
