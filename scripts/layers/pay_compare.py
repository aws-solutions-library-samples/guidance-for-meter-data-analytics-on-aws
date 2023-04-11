input = "/Users/rodekamp/Downloads/pay-equity Anonymous Wage Submissions.csv"
output = "/Users/rodekamp/Downloads/pay_cleaned.csv"

with open(input, 'r', encoding='utf-8') as infile, open(output, 'w') as outfile:
    #outfile.write(header)
    for line in infile:
        if line.startswith("2023"):
            print(line)
        #splited = line.split(",")
        #newline = "{},{},{}\n".format(splited[0].replace("MAC",""),splited[2],splited[3])
            outfile.write(line)