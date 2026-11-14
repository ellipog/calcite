import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

// Prints, for categories.calx, the runs of code points Java's Character.getType puts in
// NON_SPACING_MARK, as "mn <first>;<last>" lines in hex, and the runs of UTF-16 units
// Character.isLetterOrDigit(char) takes, as "ld <first>;<last>" lines. Black-box: it only calls
// the JDK's public API.
public class Categories {
    static void run(BufferedWriter out, String kind, int first, int last) throws Exception {
        out.write(String.format(Locale.ROOT, "%s %X;%X\n", kind, first, last));
    }

    public static void main(String[] args) throws Exception {
        BufferedWriter out = new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8));
        int start = -1;
        for (int cp = 0; cp <= Character.MAX_CODE_POINT + 1; cp++) {
            boolean in = cp <= Character.MAX_CODE_POINT && Character.getType(cp) == Character.NON_SPACING_MARK;
            if (in && start < 0) {
                start = cp;
            } else if (!in && start >= 0) {
                run(out, "mn", start, cp - 1);
                start = -1;
            }
        }
        for (int c = 0; c <= 0x10000; c++) {
            boolean in = c <= 0xFFFF && Character.isLetterOrDigit((char) c);
            if (in && start < 0) {
                start = c;
            } else if (!in && start >= 0) {
                run(out, "ld", start, c - 1);
                start = -1;
            }
        }
        out.flush();
    }
}
