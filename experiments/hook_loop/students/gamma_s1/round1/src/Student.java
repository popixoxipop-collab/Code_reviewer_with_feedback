/**
 * 학생 한 명의 이름과 시험 점수를 담는 데이터 클래스.
 */
public class Student {

    private String name;
    private double score;

    public Student(String name, double score) {
        this.name = name;
        this.score = score;
    }

    public String getName() {
        return name;
    }

    public double getScore() {
        return score;
    }

    @Override
    public String toString() {
        return name + " : " + score + "점";
    }
}
