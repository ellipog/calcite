package calcite.rig.vanilla;

/** The case is malformed: a missing field, a wrong type, an unknown operation. Reported as `error`. */
final class CaseError extends RuntimeException {
    CaseError(String message) {
        super(message);
    }
}
