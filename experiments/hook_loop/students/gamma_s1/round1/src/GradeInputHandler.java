import java.util.Scanner;

/**
 * Scanner를 이용해 학생 이름과 점수를 입력받는 클래스.
 */
public class GradeInputHandler {

    private Scanner scanner;

    public GradeInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    /**
     * 지정한 인원 수만큼 학생 이름과 점수를 입력받아 배열로 반환한다.
     *
     * @param count 입력받을 학생 수
     * @return 입력된 Student 배열
     */
    public Student[] inputStudents(int count) {
        Student[] students = new Student[count];

        for (int i = 0; i < count; i++) {
            System.out.println("[" + (i + 1) + "번째 학생]");

            System.out.print("이름 입력: ");
            String name = scanner.nextLine();

            double score = readScore();

            students[i] = new Student(name, score);
        }

        return students;
    }

    /**
     * 점수를 입력받는다. 숫자가 아닌 값이 들어오면 다시 입력받는다.
     */
    private double readScore() {
        while (true) {
            System.out.print("점수 입력: ");
            String input = scanner.nextLine();

            try {
                return Double.parseDouble(input);
            } catch (NumberFormatException e) {
                System.out.println("숫자만 입력해주세요.");
            }
        }
    }
}
